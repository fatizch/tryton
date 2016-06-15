import pydot
import datetime
import lxml

from sql.conditionals import Coalesce

from trytond.model import fields as tryton_fields, Unique
from trytond.pool import PoolMeta, Pool
from trytond.rpc import RPC
from trytond.pyson import Eval, Not, And, Bool
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateAction, StateView, Button

from trytond.modules.cog_utils import utils, model, fields
from trytond.modules.process import ProcessFramework


__metaclass__ = PoolMeta
__all__ = [
    'Status',
    'ProcessAction',
    'ProcessTransition',
    'GenerateGraph',
    'ProcessLog',
    'CogProcessFramework',
    'ProcessStepRelation',
    'Process',
    'ViewDescription',
    'ProcessStep',
    'ProcessStart',
    'ProcessFinder',
    'ProcessEnd',
    'ProcessResume',
    ]


class Status(model.CoopSQL):
    __name__ = 'process.status'

    @classmethod
    def _export_skips(cls):
        result = super(Status, cls)._export_skips()
        result.add('relations')
        return result


class ProcessAction(model.CoopSQL):
    __name__ = 'process.action'

    @classmethod
    def _export_light(cls):
        return set(['on_model'])

    def execute(self, target):
        with model.error_manager():
            super(ProcessAction, self).execute(target)


class ProcessTransition(model.CoopSQL):
    __name__ = 'process.transition'

    pyson_choice = fields.Char('Choice', states={
            'invisible': Eval('kind') != 'choice'})
    pyson_description = fields.Char('Pyson Description', states={
            'invisible': Eval('kind') != 'choice'})
    choice_if_true = fields.Many2One('process.transition',
        'Transition if True', states={'invisible': Eval('kind') != 'choice'},
        domain=[
            ('kind', '=', 'calculated'),
            ('main_model', '=', Eval('_parent_on_process', {}).get(
                'on_model'))], ondelete='RESTRICT')
    choice_if_false = fields.Many2One('process.transition',
        'Transition if False', states={
            'invisible': Eval('kind') != 'choice'}, domain=[
            ('kind', '=', 'calculated'),
            ('main_model', '=', Eval('_parent_on_process', {}).get(
                'on_model'))], ondelete='RESTRICT')

    @classmethod
    def __setup__(cls):
        super(ProcessTransition, cls).__setup__()
        cls.kind.selection.append(('calculated', 'Calculated'))
        cls.from_step.domain.extend([
                ('main_model', '=', Eval('_parent_on_process', {}).get(
                    'on_model'))])
        cls.to_step.domain.extend([
                ('main_model', '=', Eval('_parent_on_process', {}).get(
                    'on_model'))])

        cls._error_messages.update({
                'missing_pyson': 'Pyson expression and description is '
                'mandatory',
                'missing_choice': 'Both choices must be filled !',
                })

        cls._constraints += [
            ('check_pyson', 'missing_pyson'),
            ('check_choices', 'missing_choice'),
            ]

    @classmethod
    def view_attributes(cls):
        return super(ProcessTransition, cls).view_attributes() + [
            ('/form/group[@id="methods"]', 'states',
                {'invisible': Eval('kind') == 'choice'}),
            ]

    @classmethod
    def _export_light(cls):
        return set(
            ['choice_if_true', 'choice_if_false', 'from_step', 'to_step'])

    def execute(self, target):
        if self.kind != 'choice':
            return super(ProcessTransition, self).execute(target)
        result = utils.pyson_result(self.pyson_choice, target)
        if result:
            return self.choice_if_true.execute(target)
        else:
            return self.choice_if_false.execute(target)

    def get_rec_name(self, name):
        if self.kind != 'choice':
            return super(ProcessTransition, self).get_rec_name(name)
        return self.pyson_description

    def build_button(self):
        if self.kind != 'choice':
            return super(ProcessTransition, self).build_button()
        xml = '<button string="%s" name="_button_transition_%s_%s"/>' % (
            self.get_rec_name(''), self.on_process.id, self.id)
        return xml

    def check_pyson(self):
        if self.kind != 'choice':
            return True
        if not self.pyson_choice or not self.pyson_description:
            return False
        return True

    def check_choices(self):
        if self.kind != 'choice':
            return True
        if not self.choice_if_true or not self.choice_if_false:
            return False
        return True

    def get_pyson_readonly(self):
        result = super(ProcessTransition, self).get_pyson_readonly()
        if result:
            return result
        # Every step should be executable, unless its pyson says no
        if self.kind == 'standard' and \
                self.to_step.get_pyson_for_button():
            result = self.to_step.pyson
        else:
            result = 'False'
        return result


class ProcessLog(model.CoopSQL, model.CoopView):
    'Process Log'

    __name__ = 'process.log'

    user = fields.Many2One('res.user', 'User', ondelete='RESTRICT')
    from_state = fields.Many2One('process-process.step', 'From State',
        ondelete='SET NULL')
    to_state = fields.Many2One('process-process.step', 'To State', select=True,
        ondelete='SET NULL')
    start_time = fields.DateTime('Start Time', readonly=True)
    start_time_str = fields.Function(
        fields.Char('Start Time'),
        'on_change_with_start_time_str')
    end_time = fields.DateTime('End Time', readonly=True)
    end_time_str = fields.Function(
        fields.Char('End Time'),
        'on_change_with_end_time_str')
    description = fields.Text('Description')
    task = fields.Reference(
        'Task', 'get_task_models', select=True, required=True)
    locked = fields.Boolean('Lock', select=True)
    latest = fields.Boolean('Latest', select=True)
    session = fields.Char('Session')

    @classmethod
    def default_latest(cls):
        return True

    @fields.depends('end_time')
    def on_change_with_end_time_str(self, name=None):
        return Pool().get('ir.date').datetime_as_string(self.end_time)

    @fields.depends('start_time')
    def on_change_with_start_time_str(self, name=None):
        return Pool().get('ir.date').datetime_as_string(self.start_time)

    @staticmethod
    def order_end_time_str(tables):
        table, _ = tables[None]
        return [Coalesce(table.start_time, datetime.date.max)]

    @staticmethod
    def order_start_time_str(tables):
        table, _ = tables[None]
        return [Coalesce(table.end_time, datetime.date.min)]

    @classmethod
    def create(cls, values):
        for value in values:
            previous_latest = cls.search([
                ('task', '=', value['task']),
                ('latest', '=', True)])
            if previous_latest:
                previous_latest = previous_latest[0]
                previous_latest.latest = False
                previous_latest.save()
        return super(ProcessLog, cls).create(values)

    @classmethod
    def get_task_models(cls):
        Model = Pool().get('ir.model')
        good_models = Model.search([('is_workflow', '=', True)])
        return [(model.model, model.name) for model in good_models]

    def get_rec_name(self, name):
        # TODO: There should not be logs without tasks
        if not (hasattr(self, 'task') and self.task):
            return ''
        return self.task.get_rec_name(None)

    @classmethod
    def default_start_time(cls):
        return datetime.datetime.now()


class CogProcessFramework(ProcessFramework, model.CoopView):
    'Cog Process Framework'

    logs = fields.One2Many('process.log', 'task', 'Task', delete_missing=True)
    current_log = fields.Function(
        fields.Many2One('process.log', 'Current Log'),
        'get_current_log')
    current_state_name = fields.Function(
        fields.Char('Current State In Process'), 'get_current_state_name')

    @classmethod
    def __setup__(cls):
        super(CogProcessFramework, cls).__setup__()
        cls._error_messages.update({
                'lock_fault': 'Object %s is currently locked by user %s',
                })
        cls._buttons.update({
                'button_resume': {
                    'invisible': Not(Bool(Eval('current_state', False))),
                        }
                    })
        cls.__rpc__.update({
                'button_delete_task': RPC(instantiate=0, readonly=0),
                'button_hold_task': RPC(instantiate=0, readonly=0),
                })

    @classmethod
    def _export_skips(cls):
        return (super(CogProcessFramework, cls)._export_skips() |
            set(['logs']))

    @classmethod
    @model.CoopView.button_action('process_cog.act_resume_process')
    def button_resume(cls, objects):
        pass

    @classmethod
    def button_delete_task(cls, objects):
        return 'delete,close'

    @classmethod
    def button_hold_task(cls, objects):
        Log = Pool().get('process.log')
        logs = []
        for obj in objects:
            obj.current_log.locked = False
            logs.append(obj.current_log)
        if logs:
            Log.save(logs)
        return 'close'

    def get_current_state_name(self, name):
        if self.current_state:
            return self.current_state.step.fancy_name
        else:
            return None

    def get_current_log(self, name=None):
        if not (hasattr(self, 'id') and self.id):
            return None
        Log = Pool().get('process.log')
        current_log = Log.search([
                ('task', '=', utils.convert_to_reference(self)),
                ('latest', '=', True)])
        return current_log[0].id if current_log else None

    @classmethod
    def write(cls, *args):
        Log = Pool().get('process.log')
        actions = iter(args)
        zipped = zip(actions, actions)
        for instances, _ in zipped:
            for instance in instances:
                if instance.current_log and instance.current_log.locked:
                    if instance.current_log.user.id != Transaction().user:
                        cls.raise_user_error('lock_fault', (
                                instance.get_rec_name(None),
                                instance.current_log.user.get_rec_name(None)))
        super(CogProcessFramework, cls).write(*args)

        good_session = Transaction().context.get('session')
        for instances, _ in zipped:
            for instance in instances:
                good_log = instance.current_log
                if (not good_log or good_log.to_state is None and
                        not instance.current_state):
                    continue
                if (good_log.session != good_session or
                        good_log.to_state is None and instance.current_state):
                    good_log.latest = False
                    good_log.save()
                    old_log = good_log
                    good_log = Log()
                    good_log.session = good_session
                    if not Transaction().context.get('set_empty_process_user',
                            False):
                        good_log.user = Transaction().user
                    good_log.start_time = datetime.datetime.now()
                    if not (hasattr(old_log, 'to_state') and old_log.to_state):
                        good_log.from_state = instance.current_state
                    else:
                        good_log.from_state = old_log.to_state
                    good_log.latest = True
                    good_log.task = instance
                good_log.to_state = instance.current_state
                good_log.end_time = datetime.datetime.now()
                if instance.current_state is None:
                    good_log.locked = False
                good_log.save()

    @classmethod
    def create(cls, values):
        instances = super(CogProcessFramework, cls).create(values)
        Log = Pool().get('process.log')
        good_session = Transaction().context.get('session')
        for instance in instances:
            log = Log()
            log.user = Transaction().user
            log.task = utils.convert_to_reference(instance)
            log.start_time = datetime.datetime.now()
            log.end_time = datetime.datetime.now()
            log.to_state = instance.current_state
            log.session = good_session
            log.save()
        return instances

    @classmethod
    def delete(cls, records):
        # Delete logs
        Log = Pool().get('process.log')
        Log.delete(Log.search([('task', 'in', [
            utils.convert_to_reference(x) for x in records])]))
        super(CogProcessFramework, cls).delete(records)

    def get_next_execution(self):
        if not self.current_state:
            return
        from_step = self.current_state.step
        for_process = self.current_state.process
        return for_process.get_next_execution(from_step, self)

    def get_previous_execution(self):
        if not self.current_state:
            return
        from_step = self.current_state.step
        for_process = self.current_state.process
        return for_process.get_previous_execution(from_step, self)

    @classmethod
    def build_instruction_next_method(cls, process, data):
        def next(works):
            for work in works:
                good_exec = work.get_next_execution()
                if not good_exec:
                    result = None
                    break
                with Transaction().set_context(after_executed=True):
                    if good_exec == 'complete':
                        result = cls.build_instruction_complete_method(
                            process, None)([work])
                    else:
                        result = good_exec.execute(work)
                        work.save()
            return result
        return next

    @classmethod
    def build_instruction_previous_method(cls, process, data):
        def previous(works):
            for work in works:
                good_exec = work.get_previous_execution()
                if good_exec:
                    good_exec.execute(work)
                    work.save()

        return previous

    @classmethod
    def build_instruction_step_method(cls, process, data):
        def button_step_generic(works):
            ProcessStep = Pool().get('process.step')
            target = ProcessStep(data[1])
            result = None
            for work in works:
                result = target.execute(work)
                work.save()
            return result

        return button_step_generic

    @classmethod
    def button_next_states(cls, process, data):
        clause_invisible = []
        button_states = {}
        for step_relation in process.all_steps:
            step = step_relation.step
            step_pyson, auth_pyson = step.get_pyson_for_display(step_relation)
            if auth_pyson:
                clause_invisible.append(
                    'And(%s, %s)' % (step_pyson, auth_pyson))
            else:
                clause_invisible.append('%s' % step_pyson)
        if len(clause_invisible) > 1:
            button_states = {'invisible': utils.pyson_encode(
                    'Not(Or(%s))' % ', '.join(clause_invisible), True)}
        pre_validate = []
        for step_relation in process.all_steps:
            step = step_relation.step
            if step.button_domain in ('', '[]'):
                continue
            pre_validate.append("If(Eval('current_state', 0) == %i, %s, [])" %
                (step_relation.id, step.button_domain))
        if not pre_validate:
            return button_states
        button_states['pre_validate'] = utils.pyson_encode(
            '[%s]' % ', '.join(pre_validate), True)
        return button_states

    @classmethod
    def button_previous_states(cls, process, data):
        result = cls.button_next_states(process, data)
        result.pop('pre_validate', None)
        return result

    @classmethod
    def button_step_states(cls, process, step_data):
        if process.custom_transitions and \
                not process.steps_implicitly_available:
            return {'readonly': True}
        pool = Pool()
        ProcessStep = pool.get('process.step')
        from_step, to_step = ProcessStep.browse(map(int, step_data))
        result = {}
        if to_step.pyson:
            result['readonly'] = utils.pyson_encode(to_step.pyson, True)
        if from_step.button_domain and process.intermediate_steps(from_step,
                to_step):
            result['pre_validate'] = utils.pyson_encode(
                from_step.button_domain, True)
        result['invisible'] = utils.pyson_encode(
            "Eval('current_state', -1) != %i" % (
                process.get_step_relation(from_step).id), True)
        return result

    @classmethod
    def button_complete_states(cls, process, step_relation):
        if process.custom_transitions and \
                not process.steps_implicitly_available:
            return {'readonly': True}
        return {}

    @classmethod
    def build_instruction_complete_method(cls, process, data):
        pool = Pool()
        Action = pool.get('ir.action')
        ModelData = pool.get('ir.model.data')
        action_id = Action.get_action_id(ModelData.get_id('process_cog',
                'act_end_process'))

        def button_complete_generic(works):
            for work in works:
                work.current_state.step.execute_after(work)
                work.current_state = None
                work.save()
            if process.close_tab_on_completion:
                return 'close'
            return action_id

        return button_complete_generic

    def set_state(self, value, process_name=None):
        super(CogProcessFramework, self).set_state(value, process_name)
        if self.current_state:
            authorizations = self.current_state.step.authorizations
            visible = len(authorizations) == 0
            for elem in authorizations:
                visible = visible and \
                    elem.id in Transaction().context.get('groups')
        else:
            visible = False
        if visible:
            return
        self.current_log.locked = False
        self.current_log.end_time = datetime.datetime.now()
        self.current_log.to_state = self.current_state
        self.current_log.save()

    @classmethod
    def notify_events(cls, objects, event_code, description=None, **kwargs):
        Pool().get('event').notify_events(objects, event_code, description,
            **kwargs)


class Process(model.CoopSQL, model.TaggedMixin):
    __name__ = 'process'
    _func_key = 'technical_name'

    with_prev_next = fields.Boolean('With Previous / Next button')
    custom_transitions = fields.Boolean('Custom Transitions')
    steps_implicitly_available = fields.Boolean('Steps Implicitly Available',
        states={'invisible': ~Eval('custom_transitions')})
    complete_message = fields.Char('Confirmation Message for Completion',
        states={'invisible': Bool(Eval('custom_transitions', False))},
        help='A confirmation message that will be displayed when the user '
        'clicks the "Terminate" button at the end of the process',
        translate=True)
    kind = fields.Selection([('', '')], 'Kind')
    close_tab_on_completion = fields.Boolean('Close Tab On Completion')
    delete_button = fields.Char('Delete Button Name', help='If not null, a '
        'button will be added on the view with the given name, which will '
        'allow to delete the current task')
    hold_button = fields.Char('Hold Button Name', help='If not null, a '
        'button will be added on the view with the given name, which will '
        'allow to set the current task on hold')

    @classmethod
    def __setup__(cls):
        super(Process, cls).__setup__()
        cls.transitions.states['invisible'] = ~Eval('custom_transitions')
        cls.transitions.depends.append('custom_transitions')
        cls._error_messages.update({
                'button_delete_confirm': 'The current record (%s) will be '
                'deleted, are you sure you want to proceed ?',
                'previous_button_label': 'Previous',
                'next_button_label': 'Next',
                })

    @classmethod
    def _export_skips(cls):
        return super(Process, cls)._export_skips() | {'menu_items',
            'steps_to_display', 'action_windows'}

    @classmethod
    def _export_light(cls):
        result = super(Process, cls)._export_light()
        result.add('on_model')
        return result

    @classmethod
    def _post_import(cls, processes):
        cls.update_view(processes)

    @classmethod
    def default_with_prev_next(cls):
        return True

    @classmethod
    def default_custom_transitions(cls):
        return False

    @classmethod
    def default_steps_implicitly_available(cls):
        return True

    def get_next_execution(self, from_step, for_task):
        from_step.execute_after(for_task)
        cur_step_found = False
        result = None
        for step_relation in self.all_steps:
            if step_relation.step == from_step:
                cur_step_found = True
                if from_step.id == self.all_steps[-1].step.id:
                    # Check there is no "complete" button
                    if for_task.button_is_active('_button_complete_%s_%s' % (
                            self.id, self.all_steps[-1].id)):
                        result = 'complete'
                        break
            if not cur_step_found:
                continue
            if self.custom_transitions:
                for trans in self.transitions:
                    if not trans.from_step == from_step:
                        continue
                    if not trans.to_step == step_relation.step:
                        if trans.kind != 'complete':
                            continue
                    if not for_task.is_button_available(self, trans):
                        continue
                    result = trans
                    break
            if for_task.is_button_available(self, step_relation.step):
                result = step_relation.step
                break
        return result

    def get_previous_execution(self, from_step, for_task):
        cur_step_found = False
        for step_relation in reversed(self.all_steps):
            if step_relation.step == from_step:
                cur_step_found = True
            if not cur_step_found:
                continue
            # First we look for a matching transition
            if self.custom_transitions:
                for trans in self.transitions:
                    if not trans.from_step == from_step:
                        continue
                    if not trans.to_step == step_relation.step:
                        continue
                    if not for_task.is_button_available(self, trans):
                        continue
                    return trans
            if for_task.is_button_available(self, step_relation.step):
                return step_relation.step

    def get_middle_buttons(self):
        middle_buttons = []
        if self.delete_button:
            middle_buttons.append(
                '<button string="%s" name="button_delete_task" '
                'icon="tryton-delete" confirm="%s"/>' % (self.delete_button,
                    self.raise_user_error('button_delete_confirm',
                        (self.on_model.rec_name,), raise_exception=False)))
        if self.hold_button:
            middle_buttons.append(
                '<button string="%s" name="button_hold_task" '
                'icon="tryton-save"/>' % self.hold_button)
        return middle_buttons

    def get_xml_footer(self, colspan=4):
        xml = ''
        middle_buttons = self.get_middle_buttons()
        xml += '<group id="group_prevnext" colspan="4" col="%s">' % (
            8 + len(middle_buttons))
        if self.with_prev_next:
            xml += '<button string="%s"' % self.raise_user_error(
                'previous_button_label', raise_exception=False)
            xml += ' name="_button_previous_%s"/>' % self.id
        if middle_buttons:
            xml += '<group id="void_l" colspan="3"/>'
            xml += ''.join(middle_buttons)
            xml += '<group id="void_r" colspan="3"/>'
        else:
            xml += '<group id="void" colspan="6"/>'
        if self.with_prev_next:
            xml += '<button string="%s" ' % self.raise_user_error(
                'next_button_label', raise_exception=False)
            xml += 'name="_button_next_%s"/>' % self.id
        xml += '</group>'
        xml += '<newline/>'
        xml += super(Process, self).get_xml_footer(colspan)
        return xml

    def calculate_buttons_for_step(self, step_relation):
        if self.custom_transitions:
            return super(Process, self).calculate_buttons_for_step(
                step_relation)
        result = {}
        for relation in self.all_steps:
            result[relation.step.id] = ('step', relation.step)
        return result

    def build_step_buttons(self, step_relation):
        nb, result = super(Process, self).build_step_buttons(step_relation)
        if not self.custom_transitions and self.all_steps[-1] == step_relation:
            result += '<button string="%s" ' % (self.end_step_name or
                'Complete')
            result += 'name="_button_complete_%s_%s"' % (
                self.id, step_relation.id)
            if self.complete_message:
                result += ' confirm="%s"' % self.complete_message
            result += '/>'
            nb += 1
        return nb, result

    def intermediate_steps(self, step1, step2):
        # Returns True if step1 appears before step2 in self.all_steps
        step1_rank = -1
        step2_rank = -1
        for idx, elem in enumerate(self.all_steps):
            if step1.id == elem.step.id:
                step1_rank = elem.order
                step1_idx = idx
            if step2.id == elem.step.id:
                step2_rank = elem.order
                step2_idx = idx
        if step1_rank > step2_rank:
            return []
        return map(lambda x: x.step, self.all_steps[step1_idx:step2_idx + 1])


class ProcessStepRelation(model.CoopSQL):
    __name__ = 'process-process.step'

    @classmethod
    def __setup__(cls):
        super(ProcessStepRelation, cls).__setup__()
        cls.step.domain.extend([
                ('main_model', '=', Eval('_parent_process', {}).get(
                        'on_model', 0))])
        cls.process.required = True


class ViewDescription(model.CoopSQL, model.CoopView):
    'View Description'

    __name__ = 'ir.ui.view.description'
    _func_key = 'func_key'

    the_view = fields.Many2One('ir.ui.view', 'View', states={'readonly': True},
        ondelete='SET NULL')
    view_name = fields.Char('View Name', required=True,
        states={'readonly': Eval('id', 0) > 0},
        depends=['view_name', 'view_model'])
    view_final_name = fields.Function(
        fields.Char('View Name', states={'readonly': True},
            depends=['view_name', 'view_kind', 'view_model']),
        'on_change_with_view_final_name')
    view_kind = fields.Selection([
            ('form', 'Form'),
            ('tree', 'Tree')], 'View Kind')
    input_mode = fields.Selection([
            ('classic', 'Classic'),
            ('expert', 'Expert')], 'Input Mode')
    header_line = fields.Char('Header Line',
        states={'invisible': Eval('input_mode', '') != 'expert'},
        depends=['view_string', 'nb_col', 'input_mode', 'header_line',
            'view_kind'])
    view_string = fields.Char('View String',
        states={'invisible': Eval('input_mode', '') != 'classic'},
        depends=['input_mode', 'view_model'])
    nb_col = fields.Integer('Number of columns', states={
            'invisible': Not(And(
                    Eval('input_mode', '') == 'classic',
                    Eval('view_kind', '') == 'form')),
            }, depends=['view_kind', 'input_mode'])
    view_content = fields.Text('View Content')
    view_model = fields.Many2One('ir.model', 'View Model', required=True,
        states={'readonly': Eval('id', 0) > 0}, ondelete='RESTRICT')
    for_step = fields.Many2One('process.step', 'For Step', ondelete='CASCADE',
        select=True)
    field_childs = fields.Selection('get_field_childs', 'Children field',
        depends=['view_model'], states={
            'invisible': Eval('view_kind') != 'tree'})
    func_key = fields.Function(fields.Char('Functional Key'),
        'get_func_key', searcher='search_func_key')

    @classmethod
    def __setup__(cls):
        super(ViewDescription, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('unique_fs_id', Unique(t, t.view_name, t.for_step, t.view_kind),
                'The functional id must be unique !')]
        cls.__rpc__.update({'get_field_childs': RPC(instantiate=0)})

    @classmethod
    def _export_skips(cls):
        result = super(ViewDescription, cls)._export_skips()
        result.add('the_view')
        return result

    @classmethod
    def _export_light(cls):
        result = super(ViewDescription, cls)._export_light()
        result.add('view_model')
        return result

    @classmethod
    def _post_import(cls, views):
        for view in views:
            view.the_view = view.create_update_view()
            view.save()

    @classmethod
    def default_nb_col(cls):
        return 4

    @classmethod
    def default_view_kind(cls):
        return 'form'

    @classmethod
    def default_input_mode(cls):
        return 'classic'

    @fields.depends('view_model')
    def on_change_with_field_childs(self):
        if not (hasattr(self, 'view_model') and self.view_model):
            return ''

    @fields.depends('view_model')
    def get_field_childs(self):
        if not (hasattr(self, 'view_model') and self.view_model):
            return [('', '')]
        ViewModel = Pool().get(self.view_model.model)
        return [
            (field_name, field.string)
            for field_name, field in ViewModel._fields.iteritems()
            if isinstance(field, tryton_fields.One2Many)] + [('', '')]

    def get_func_key(self, name):
        return '%s|%s' % ((self.for_step.technical_name, self.view_name))

    @classmethod
    def default_view_final_name(cls):
        return 'step_%s__form' % Transaction().context.get('for_step_name', '')

    @fields.depends('view_string', 'nb_col', 'input_mode', 'header_line',
        'view_kind')
    def on_change_with_header_line(self):
        if self.input_mode == 'expert':
            return self.header_line
        xml = 'string="%s" ' % self.view_string
        if hasattr(self, 'view_kind') and self.view_kind == 'form':
            xml += 'col="%s" ' % self.nb_col
        return xml

    @fields.depends('view_model')
    def on_change_with_view_string(self):
        if not (hasattr(self, 'view_model') and self.view_model):
            return ''
        # TODO : Get the good (translated) name
        return self.view_model.name

    @fields.depends('view_name', 'view_model')
    def on_change_with_view_name(self):
        if (hasattr(self, 'view_model') and self.view_model):
            if not (hasattr(self, 'attribute') and self.attribute):
                return self.view_model.model.split('.')[1].replace('.', '_')

    @fields.depends('view_name', 'view_kind', 'view_model')
    def on_change_with_view_final_name(self, name=None):
        if (hasattr(self, 'for_step') and self.for_step):
            the_step = self.for_step.technical_name
        else:
            the_step = Transaction().context.get('for_step_name', '')
        return '_extra_views.step_%s_%s_%s' % (
            the_step, self.on_change_with_view_name(), self.view_kind)

    def create_update_view(self):
        if (hasattr(self, 'the_view') and self.the_view):
            the_view = self.the_view
        else:
            View = Pool().get('ir.ui.view')
            the_view = View()
            the_view.module = '_extra_views'
            the_view.name = self.on_change_with_view_final_name()[13:]
        the_view.model = self.view_model.model
        the_view.priority = 1000
        the_view.field_childs = self.field_childs if hasattr(
            self, 'field_childs') else ''
        the_view.type = self.view_kind
        the_view.data = '<?xml version="1.0"?>'
        the_view.data += '<%s %s>' % (
            self.view_kind, self.on_change_with_header_line())
        the_view.data += self.view_content
        if self.view_kind == 'form':
            the_view.data += '</form>'
        elif self.view_kind == 'tree':
            the_view.data += '</tree>'
        the_view.save()
        ModelData = Pool().get('ir.model.data')
        good_data = ModelData.search([
                ('module', '=', '_extra_views'),
                ('fs_id', '=', the_view.name),
                ('model', '=', 'ir.ui.view')])
        if not good_data:
            data = ModelData()
            data.module = '_extra_views'
            data.model = 'ir.ui.view'
            data.fs_id = the_view.name
            data.db_id = the_view.id
            data.save()
        return the_view

    @classmethod
    def create(cls, values):
        view_descs = super(ViewDescription, cls).create(values)
        for view_desc in view_descs:
            the_view = view_desc.create_update_view()
            if not view_desc.the_view:
                cls.write([view_desc], {'the_view': the_view})
        return view_descs

    @classmethod
    def write(cls, *args):
        super(ViewDescription, cls).write(*args)
        actions = iter(args)
        for instances, values in zip(actions, actions):
            if 'the_view' in values:
                continue
            for view_desc in instances:
                the_view = view_desc.create_update_view()
                if not view_desc.the_view:
                    cls.write([view_desc], {'the_view': the_view})

    @classmethod
    def delete(cls, records):
        to_delete = [rec.the_view for rec in records if rec.the_view]
        super(ViewDescription, cls).delete(records)
        ModelData = Pool().get('ir.model.data')
        good_data = ModelData.search([
                ('module', '=', '_extra_views'),
                ('model', '=', 'ir.ui.view'),
                ('db_id', 'in', [x.id for x in to_delete])])
        ModelData.delete(good_data)
        View = Pool().get('ir.ui.view')
        View.delete(to_delete)

    @classmethod
    def search_func_key(cls, name, clause):
        assert clause[1] == '='
        if '|' in clause[2]:
            operands = clause[2].split('|')
            if len(operands) == 2:
                step_code, view_code = clause[2].split('|')
                return [('for_step.technical_name', clause[1], step_code),
                    ('view_name', clause[1], view_code)]
            else:
                return [('id', '=', None)]
        else:
            return ['OR',
                [('for_step.technical_name',) + tuple(clause[1:])],
                [('view_name',) + tuple(clause[1:])],
                ]


class ProcessStep(model.CoopSQL, model.TaggedMixin):
    __name__ = 'process.step'
    _func_key = 'technical_name'

    pyson = fields.Char('Pyson Constraint')
    button_domain = fields.Char('Button Domain')
    custom_views = fields.One2Many('ir.ui.view.description', 'for_step',
        'Custom Views', context={'for_step_name': Eval('technical_name', '')},
        states={'readonly': ~Eval('technical_name')},
        target_not_required=True)
    main_model = fields.Many2One('ir.model', 'Main Model', domain=[
            ('is_workflow', '=', True),
            ('model', '!=', 'process.process_framework'),
            ], depends=['processes'], required=True, ondelete='RESTRICT')
    static_view = fields.Many2One('ir.ui.view', 'Static View',
        states={'invisible': ~Eval('main_model')},
        domain=[('model', '=', Eval('main_model_name')),
            ('type', '=', 'form')],
        depends=['main_model', 'main_model_name'])
    main_model_name = fields.Function(
        fields.Char('Main Model Name', states={'invisible': True}),
        'on_change_with_main_model_name')

    @classmethod
    def __setup__(cls):
        super(ProcessStep, cls).__setup__()
        cls.step_xml.states.update({
                'readonly': Bool(Eval('static_view', False))})
        cls.step_xml.depends.append('static_view')

    @classmethod
    def copy(cls, steps, default=None):
        if default is None:
            default = {}
        default.setdefault('processes', None)
        return super(ProcessStep, cls).copy(steps, default=default)

    @classmethod
    def is_master_object(cls):
        return True

    @classmethod
    def _export_skips(cls):
        result = super(ProcessStep, cls)._export_skips()
        result.add('processes')
        return result

    @classmethod
    def _export_light(cls):
        result = super(ProcessStep, cls)._export_light()
        result.add('main_model')
        return result

    @classmethod
    def default_button_domain(cls):
        return '[]'

    @fields.depends('main_model')
    def on_change_with_main_model_name(self, name=None):
        return getattr(self.main_model, 'model', '')

    @fields.depends('colspan', 'static_view', 'step_xml')
    def on_change_static_view(self):
        if not self.static_view:
            return
        view_xml = utils.get_view_complete_xml(
            Pool().get(self.static_view.model), self.static_view)
        xml = lxml.etree.fromstring(view_xml)
        nb_col = int(xml.get('col', '4'))
        self.colspan = nb_col
        self.step_xml = '\n'.join([lxml.etree.tostring(x, pretty_print=True)
                for x in xml])
        return

    @fields.depends('main_model', 'static_view')
    def on_change_main_model(self):
        if not self.main_model:
            self.static_view = None

    def get_pyson_for_button(self):
        return self.pyson or ''

    def execute(self, target):
        result = None
        origin = target.current_state.step
        intermediates = target.current_state.process.intermediate_steps(
            origin, self)
        for idx, origin in enumerate(intermediates):
            if result:
                origin.execute_before(target)
                target.set_state(origin)
                return result
            if idx == len(intermediates) - 1:
                continue
            if idx != 0:
                result = origin.execute_before(target)
                if result:
                    target.set_state(origin)
                    return result
            result = origin.execute_after(target)
        result = self.execute_before(target) if not result else result
        target.set_state(self, target.current_state.process.technical_name)
        return result


class ProcessStart(model.CoopView):
    'Process Start'

    __name__ = 'process.start'

    model = fields.Many2One('ir.model', 'Model',
        domain=[('is_workflow', '=', 'True')],
        states={'readonly': True, 'invisible': True})
    good_process = fields.Many2One('process', 'Good Process',
        depends=['model'], states={'invisible': True}, required=True)

    @classmethod
    def __setup__(cls):
        super(ProcessStart, cls).__setup__()
        cls.good_process.domain = cls.build_process_domain()
        cls.good_process.depends = cls.build_process_depends()

    @classmethod
    def build_process_domain(cls):
        return [('on_model', '=', Eval('model'))]

    @classmethod
    def build_process_depends(cls):
        return ['model']

    @classmethod
    def default_model(cls):
        return {}

    @fields.depends('model')
    def on_change_with_good_process(self):
        return utils.auto_complete_with_domain(self, 'good_process')


class ProcessFinder(Wizard):
    'Process Finder'

    class VoidStateAction(StateAction):
        def __init__(self):
            StateAction.__init__(self, None)

        def get_action(self):
            return None

    start_state = 'process_parameters'
    process_parameters = StateView('process.start',
        'process_cog.process_parameters_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Start Process', 'action', 'tryton-go-next',
                default=True)])
    action = VoidStateAction()

    @classmethod
    def __setup__(cls):
        super(ProcessFinder, cls).__setup__()
        cls.process_parameters.model_name = cls.get_parameters_model()
        cls.process_parameters.view = cls.get_parameters_view()

    def do_action(self, action):
        Action = Pool().get('ir.action')
        good_action = self.process_parameters.good_process.get_act_window()
        good_values = Action.get_action_values(
            'ir.action.act_window', [good_action.id])
        good_values[0]['views'] = [
            view for view in good_values[0]['views'] if view[1] == 'form']
        good_obj = self.get_or_create_object()
        if (hasattr(good_obj, 'current_state') and good_obj.current_state):
            good_obj.current_state.step.execute_before(good_obj)
        good_obj.save()
        return good_values[0], {'res_id': [good_obj.id]}

    def search_main_object(self):
        return None

    def update_main_object(self, main_obj):
        pass

    def get_or_create_object(self):
        res = self.search_main_object()
        if res:
            self.update_main_object(res)
        else:
            return self.instanciate_main_object()
        self.init_state(res)
        return res

    def init_state(self, obj):
        if not getattr(obj, 'current_state', None):
            obj.current_state = \
                self.process_parameters.good_process.all_steps[0]

    def instanciate_main_object(self):
        GoodModel = Pool().get(self.process_parameters.model.model)
        good_obj = GoodModel()
        self.init_state(good_obj)
        is_ok, errs = self.init_main_object_from_process(
            good_obj, self.process_parameters)
        if is_ok:
            return good_obj
        else:
            pass
            # TODO What if?

    def init_main_object_from_process(self, obj, process_param):
        return True, []

    @classmethod
    def get_parameters_model(cls):
        return 'process.start'

    @classmethod
    def get_parameters_view(cls):
        return 'process_cog.process_parameters_form'


class ProcessEnd(Wizard):
    'End process'

    __name__ = 'process.end'

    class VoidStateAction(StateAction):
        def __init__(self):
            StateAction.__init__(self, None)

        def get_action(self):
            return None

    start = VoidStateAction()

    def do_start(self, action):
        pool = Pool()
        ActWindow = pool.get('ir.action.act_window')
        Action = pool.get('ir.action')
        possible_actions = ActWindow.search([
                ('res_model', '=', Transaction().context.get('active_model'))])
        good_action = possible_actions[0]
        good_values = Action.get_action_values(
            'ir.action.act_window', [good_action.id])
        good_values[0]['views'] = [
            view for view in good_values[0]['views'] if view[1] == 'form']
        return good_values[0], {
            'res_id': Transaction().context.get('active_ids'),
            'extra_context': {'running_process': ''}}

    def end(self):
        return 'close'


class ProcessResume(Wizard):
    'Resume Process'

    __name__ = 'process.resume'

    start_state = 'resume'
    resume = model.VoidStateAction()

    @classmethod
    def __setup__(cls):
        super(ProcessResume, cls).__setup__()
        cls._error_messages.update({
                'no_process_found': 'No active process found',
                'lock_by_user': 'Process Locked by user',
                })

    def do_resume(self, action):
        pool = Pool()
        active_id = Transaction().context.get('active_id')
        active_model = Transaction().context.get('active_model')
        instance = pool.get(active_model)(active_id)
        if not instance.current_state:
            self.raise_user_error('no_process_found')
        Log = pool.get('process.log')
        active_logs = Log.search([
                ('latest', '=', True),
                ('task', '=', '%s,%i' % (active_model, active_id))])
        if not active_logs:
            self.raise_user_error('no_process_found')
        active_log, = active_logs
        if (active_log.locked is True and
                active_log.user.id != Transaction().user):
            self.raise_user_error('lock_by_user', (active_log.user.name,))
        process_action = instance.current_state.process.get_act_window()
        Action = pool.get('ir.action')
        process_action = Action.get_action_values(process_action.__name__,
            [process_action.id])[0]
        good_session = Transaction().context.get('session')
        new_log = Log()
        new_log.user = Transaction().user
        new_log.locked = True
        new_log.task = instance
        new_log.from_state = instance.current_state.id
        new_log.to_state = instance.current_state.id
        new_log.start_time = datetime.datetime.now()
        new_log.session = good_session
        new_log.save()

        views = process_action['views']
        if len(views) > 1:
            for view in views:
                if view[1] == 'form':
                    process_action['views'] = [view]
                    break
        return (process_action, {
                'id': active_id,
                'model': active_model,
                'res_id': [active_id],
                'res_model': active_model,
                })


class GenerateGraph:
    __name__ = 'process.generate_graph.report'

    @classmethod
    def build_transition(cls, process, step, transition, graph, nodes, edges):
        if not transition.kind == 'choice':
            super(GenerateGraph, cls).build_transition(
                process, step, transition, graph, nodes, edges)
            return
        choice_node = pydot.Node(
            transition.pyson_description,
            style='filled',
            shape='diamond',
            fillcolor='orange',
            fontname='Century Gothic',
            )
        nodes['tr%s' % transition.id] = choice_node
        choice_edge = pydot.Edge(
            nodes[transition.from_step.id],
            choice_node,
            fontname='Century Gothic',
            )
        edges[(transition.from_step.id, 'tr%s' % transition.id)] = choice_edge
        true_edge = pydot.Edge(
            choice_node,
            nodes[transition.choice_if_true.to_step.id],
            fontname='Century Gothic',
            )
        true_edge.set('len', '1.0')
        true_edge.set('constraint', '1')
        true_edge.set('weight', '0.5')
        true_edge.set('label', 'Yes')
        true_edge.set('color', 'green')
        edges[(
            'tr%s' % transition.id,
            transition.choice_if_true.to_step.id)] = true_edge
        false_edge = pydot.Edge(
            choice_node,
            nodes[transition.choice_if_false.to_step.id],
            fontname='Century Gothic',
            )
        false_edge.set('len', '1.0')
        false_edge.set('constraint', '1')
        false_edge.set('weight', '0.5')
        false_edge.set('label', 'No')
        false_edge.set('color', 'red')
        edges[(
            'tr%s' % transition.id,
            transition.choice_if_false.to_step.id)] = false_edge

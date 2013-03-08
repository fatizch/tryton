import copy
import pydot
import datetime

from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, Not, And
from trytond.model import fields
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateAction, StateView, Button

from trytond.modules.coop_utils import utils, model, date
from trytond.modules.process import ProcessFramework


__all__ = [
    'StepTransition',
    'GenerateGraph',
    'ProcessLog',
    'CoopProcessFramework',
    'ProcessStepRelation',
    'ProcessDesc',
    'XMLViewDesc',
    'StepDesc',
    'ProcessParameters',
    'ProcessFinder',
]


class StepTransition(model.CoopSQL):
    'Step Transition'

    __metaclass__ = PoolMeta
    __name__ = 'process.step_transition'

    pyson_choice = fields.Char(
        'Choice', states={'invisible': Eval('kind') != 'choice'})
    pyson_description = fields.Char(
        'Pyson Description',
        states={'invisible': Eval('kind') != 'choice'})
    choice_if_true = fields.Many2One(
        'process.step_transition',
        'Transition if True',
        states={'invisible': Eval('kind') != 'choice'},
        domain=[
            ('kind', '=', 'calculated'),
            ('main_model', '=', Eval('_parent_on_process', {}).get(
                'on_model'))],
    )
    choice_if_false = fields.Many2One(
        'process.step_transition',
        'Transition if False',
        states={'invisible': Eval('kind') != 'choice'},
        domain=[
            ('kind', '=', 'calculated'),
            ('main_model', '=', Eval('_parent_on_process', {}).get(
                'on_model'))],
    )

    @classmethod
    def __setup__(cls):
        super(StepTransition, cls).__setup__()
        kind = copy.copy(cls.kind)
        kind.selection.append(('calculated', 'Calculated'))
        setattr(cls, 'kind', kind)
        cls.from_step = copy.copy(cls.from_step)
        cls.from_step.domain.extend([
            ('main_model', '=', Eval('_parent_on_process', {}).get(
                'on_model'))])
        cls.to_step = copy.copy(cls.to_step)
        cls.to_step.domain.extend([
            ('main_model', '=', Eval('_parent_on_process', {}).get(
                'on_model'))])

        cls._error_messages.update({
            'missing_pyson': 'Pyson expression and description is mandatory',
            'missing_choice': 'Both choices must be filled !',
        })

        cls._constraints += [
            ('check_pyson', 'missing_pyson'),
            ('check_choices', 'missing_choice'),
        ]

    def execute(self, target):
        if self.kind != 'choice':
            super(StepTransition, self).execute(target)
            return
        result = utils.pyson_result(self.pyson_choice, target)
        if result:
            self.choice_if_true.execute(target)
        else:
            self.choice_if_false.execute(target)

    def get_rec_name(self, name):
        if self.kind != 'choice':
            return super(StepTransition, self).get_rec_name(name)
        return self.pyson_description

    def build_button(self):
        if self.kind != 'choice':
            return super(StepTransition, self).build_button()
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
        result = super(StepTransition, self).get_pyson_readonly()
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

    __name__ = 'coop_process.process_log'

    user = fields.Many2One('res.user', 'User')
    from_state = fields.Many2One(
        'process.process_step_relation', 'From State', ondelete='RESTRICT')
    to_state = fields.Many2One(
        'process.process_step_relation', 'To State', ondelete='RESTRICT')
    start_time = fields.DateTime('Start Time')
    end_time = fields.DateTime('End Time')
    description = fields.Text('Description')
    task = fields.Reference(
        'Task', 'get_task_models', select=True, required=True)
    locked = fields.Boolean('Lock', select=True)
    latest = fields.Boolean('Latest')
    session = fields.Char('Session')

    @classmethod
    def default_latest(cls):
        return True

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


class CoopProcessFramework(ProcessFramework):
    'Coop Process Framework'

    logs = fields.One2Many('coop_process.process_log', 'task', 'Task')
    current_log = fields.Function(
        fields.Many2One('coop_process.process_log', 'Current Log'),
        'get_current_log')

    @classmethod
    def __setup__(cls):
        super(CoopProcessFramework, cls).__setup__()
        cls._error_messages.update({
            'lock_fault': 'Object %s is currently locked by user %s',
        })

    def get_current_log(self, name):
        if not (hasattr(self, 'id') and self.id):
            return None
        Log = Pool().get('coop_process.process_log')
        current_log = Log.search([
            ('task', '=', utils.convert_to_reference(self)),
            ('latest', '=', True)])
        return current_log[0].id if current_log else None

    @classmethod
    def write(cls, instances, values):
        for instance in instances:
            if instance.current_log and instance.current_log.locked:
                if instance.current_log.user.id != Transaction().user:
                    cls.raise_user_error(
                        'lock_fault', (
                            instance.get_rec_name(None),
                            instance.current_log.user.get_rec_name(None)))
        super(CoopProcessFramework, cls).write(instances, values)
        Session = Pool().get('ir.session')
        Log = Pool().get('coop_process.process_log')
        good_session, = Session.search(
            [('create_uid', '=', Transaction().user)])
        for instance in instances:
            good_log = instance.current_log
            if good_log.session != good_session.key:
                good_log.latest = False
                good_log.save()
                old_log = good_log
                good_log = Log()
                good_log.session = good_session.key
                good_log.user = Transaction().user
                good_log.start_time = datetime.datetime.now()
                good_log.from_state = old_log.end_state
                good_log.latest = True
            good_log.to_state = instance.current_state
            good_log.end_time = datetime.datetime.now()
            if instance.current_state is None:
                good_log.locked = False
            good_log.save()

    @classmethod
    def create(cls, values):
        instances = super(CoopProcessFramework, cls).create(values)
        Log = Pool().get('coop_process.process_log')
        Session = Pool().get('ir.session')
        good_session, = Session.search(
            [('create_uid', '=', Transaction().user)])
        for instance in instances:
            log = Log()
            log.user = Transaction().user
            log.task = utils.convert_to_reference(instance)
            log.start_time = datetime.datetime.now()
            log.end_time = datetime.datetime.now()
            log.end_state = instance.current_state
            log.session = good_session.key
            log.save()
        return instances

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
                if good_exec:
                    if good_exec == 'complete':
                        cls.build_instruction_complete_method(process, None)(
                            [work])
                    else:
                        good_exec.execute(work)
                        work.save()

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
            StepDesc = Pool().get('process.step_desc')
            target = StepDesc(data[0])
            for work in works:
                target.execute(work)
                work.save()

        return button_step_generic

    @classmethod
    def button_next_states(cls, process, data):
        result = []
        for step_relation in process.all_steps:
            step = step_relation.step
            step_pyson, auth_pyson = step.get_pyson_for_display(step_relation)
            if auth_pyson:
                result.append('And(%s, %s)' % (step_pyson, auth_pyson))
            else:
                result.append('%s' % step_pyson)
        final_result = 'Not(Or(%s))' % ', '.join(result)
        return {'invisible': utils.pyson_encode(final_result, True)}

    @classmethod
    def button_previous_states(cls, process, data):
        return cls.button_next_states(process, data)

    @classmethod
    def button_step_states(cls, process, step_data):
        if process.custom_transitions and \
                not process.steps_implicitly_available:
            return {'readonly': True}
        StepDesc = Pool().get('process.step_desc')
        good_step = StepDesc(int(step_data[0]))
        if not good_step.pyson:
            return {}
        else:
            return {'readonly': utils.pyson_encode(good_step.pyson, True)}

    @classmethod
    def button_complete_states(cls, process, step_relation):
        return {}

    @classmethod
    def build_instruction_complete_method(cls, process, data):
        def button_complete_generic(works):
            for work in works:
                work.current_state = None
                work.save()

        return button_complete_generic


class ProcessDesc(model.CoopSQL):
    'Process Descriptor'

    __metaclass__ = PoolMeta
    __name__ = 'process.process_desc'

    with_prev_next = fields.Boolean('With Previous / Next button')
    custom_transitions = fields.Boolean('Custom Transitions')
    steps_implicitly_available = fields.Boolean(
        'Steps Implicitly Available',
        states={'invisible': ~Eval('custom_transitions')},
    )
    kind = fields.Selection([('', '')], 'Kind')
    start_date = fields.Date('Start Date', required=True)
    end_date = fields.Date('End Date')

    @classmethod
    def __setup__(cls):
        super(ProcessDesc, cls).__setup__()
        cls.transitions = copy.copy(cls.transitions)
        cls.transitions.states['invisible'] = ~Eval('custom_transitions')
        cls.transitions.depends.append('custom_transitions')

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
        for step_relation in self.all_steps:
            if step_relation.step == from_step:
                cur_step_found = True
                if from_step.id == self.all_steps[-1].step.id:
                    # Check there is no "complete" button
                    if for_task.button_is_active('_button_complete_%s_%s' % (
                            self.id, self.all_steps[-1].id)):
                        return 'complete'
                continue
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

    def get_previous_execution(self, from_step, for_task):
        cur_step_found = False
        for step_relation in reversed(self.all_steps):
            if step_relation.step == from_step:
                cur_step_found = True
                continue
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

    def get_xml_footer(self, colspan=4):
        xml = ''
        if self.with_prev_next:
            xml += '<group name="group_prevnext" colspan="4" col="8">'
            xml += '<button string="Previous"'
            xml += ' name="_button_previous_%s"/>' % self.id
            xml += '<group name="void" colspan="6"/>'
            xml += '<button string="Next" '
            xml += 'name="_button_next_%s"/>' % self.id
            xml += '</group>'
            xml += '<newline/>'
        xml += super(ProcessDesc, self).get_xml_footer(colspan)
        return xml

    def calculate_buttons_for_step(self, step_relation):
        if self.custom_transitions:
            return super(ProcessDesc, self).calculate_buttons_for_step(
                step_relation)
        result = {}
        for relation in self.all_steps:
            result[relation.step.id] = ('step', relation.step)
        return result

    def build_step_buttons(self, step_relation):
        nb, result = super(ProcessDesc, self).build_step_buttons(step_relation)
        if not self.custom_transitions and self.all_steps[-1] == step_relation:
            result += '<button string="Complete" '
            result += 'name="_button_complete_%s_%s"/>' % (
                self.id, step_relation.id)
            nb += 1
        return nb, result

    @classmethod
    def create(cls, values):
        for process in values:
            last_version = cls.search([
                ('on_model', '=', process['on_model']),
                ('kind', '=', process['kind']),
                ('end_date', '=', None),
                ('start_date', '<', process['start_date'])])
            if last_version:
                cls.write(last_version, {
                    'end_date': date.add_day(process['start_date'], -1)})
        return super(ProcessDesc, cls).create(values)


class ProcessStepRelation(model.CoopSQL):
    'Process to Step relation'

    __metaclass__ = PoolMeta
    __name__ = 'process.process_step_relation'

    @classmethod
    def __setup__(cls):
        super(ProcessStepRelation, cls).__setup__()
        cls.step = copy.copy(cls.step)
        cls.step.domain.extend([(
            'main_model', '=', Eval('_parent_process', {}).get(
                'on_model', 0))])


class XMLViewDesc(model.CoopSQL, model.CoopView):
    'XML View Descriptor'

    __name__ = 'coop_process.xml_view_desc'

    the_view = fields.Many2One(
        'ir.ui.view',
        'View',
        states={'readonly': True},
    )
    view_name = fields.Char(
        'View Name',
        required=True,
        states={'readonly': Eval('id', 0) > 0},
        on_change_with=['view_name', 'view_model'],
        depends=['view_name', 'view_model'],
    )
    view_final_name = fields.Function(
        fields.Char(
            'View Name',
            states={'readonly': True},
            on_change_with=['view_name', 'view_kind'],
            depends=['view_name', 'view_kind', 'view_model'],
        ),
        'on_change_with_view_final_name',
    )
    view_kind = fields.Selection(
        [('form', 'Form'), ('tree', 'Tree')],
        'View Kind',
    )
    input_mode = fields.Selection(
        [('classic', 'Classic'), ('expert', 'Expert')],
        'Input Mode',
    )
    header_line = fields.Char(
        'Header Line',
        states={'invisible': Eval('input_mode', '') != 'expert'},
        on_change_with=[
            'view_string', 'nb_col', 'input_mode', 'header_line', 'view_kind'],
        depends=[
            'view_string', 'nb_col', 'input_mode', 'header_line', 'view_kind'],
    )
    view_string = fields.Char(
        'View String',
        states={'invisible': Eval('input_mode', '') != 'classic'},
        on_change_with=['view_model'],
        depends=['input_mode', 'view_model'],
    )
    nb_col = fields.Integer(
        'Number of columns',
        states={
            'invisible': Not(And(
                Eval('input_mode', '') == 'classic',
                Eval('view_kind', '') == 'form')),
        },
        depends=['view_kind', 'input_mode'],
    )
    view_content = fields.Text('View Content')
    view_model = fields.Many2One(
        'ir.model',
        'View Model',
        required=True,
        states={'readonly': Eval('id', 0) > 0},
    )
    for_step = fields.Many2One(
        'process.step_desc',
        'For Step',
        ondelete='CASCADE',
    )

    @classmethod
    def __setup__(cls):
        super(XMLViewDesc, cls).__setup__()
        cls._sql_constraints += [
            ('unique_fs_id', 'UNIQUE(view_name, for_step, view_kind)',
                'The functional id must be unique !')]

    @classmethod
    def default_nb_col(cls):
        return 4

    @classmethod
    def default_view_kind(cls):
        return 'form'

    @classmethod
    def default_input_mode(cls):
        return 'classic'

    @classmethod
    def default_view_final_name(cls):
        return 'step_%s__form' % Transaction().context.get('for_step_name', '')

    def on_change_with_header_line(self):
        if self.input_mode == 'expert':
            return self.header_line
        if self.view_kind == 'tree':
            xml = '<tree '
        elif self.view_kind == 'form':
            xml = '<form '
        xml += 'string="%s" ' % self.view_string
        if self.view_kind == 'form':
            xml += 'col="%s" ' % self.nb_col
        xml += '>'
        return xml

    def on_change_with_view_string(self):
        if not (hasattr(self, 'view_model') and self.view_model):
            return ''
        # TODO : Get the good (translated) name
        return self.view_model.name

    def on_change_with_view_name(self):
        if (hasattr(self, 'view_model') and self.view_model):
            if not (hasattr(self, 'attribute') and self.attribute):
                return self.view_model.model.split('.')[1].replace('.', '_')

    def on_change_with_view_final_name(self, name=None):
        if (hasattr(self, 'for_step') and self.for_step):
            the_step = self.for_step.technical_name
        else:
            the_step = Transaction().context.get('for_step_name', '')
        return 'step_%s_%s_%s' % (the_step, self.view_name, self.view_kind)

    def create_update_view(self):
        if (hasattr(self, 'the_view') and self.the_view):
            the_view = self.the_view
        else:
            View = Pool().get('ir.ui.view')
            the_view = View()
            the_view.module = 'process'
            the_view.name = self.on_change_with_view_final_name()
        the_view.model = self.view_model.model
        the_view.priority = 1000
        the_view.type = self.view_kind
        the_view.data = '<?xml version="1.0"?>'
        the_view.data += self.on_change_with_header_line()
        the_view.data += self.view_content
        if self.view_kind == 'form':
            the_view.data += '</form>'
        elif self.view_kind == 'tree':
            the_view.data += '</tree>'
        the_view.save()
        ModelData = Pool().get('ir.model.data')
        good_data = ModelData.search([
            ('module', '=', 'process'),
            ('fs_id', '=', the_view.name),
            ('model', '=', 'ir.ui.view')])
        if not good_data:
            data = ModelData()
            data.module = 'process'
            data.model = 'ir.ui.view'
            data.fs_id = the_view.name
            data.db_id = the_view.id
            data.save()
        return the_view

    @classmethod
    def create(cls, values):
        view_descs = super(XMLViewDesc, cls).create(values)
        for view_desc in view_descs:
            the_view = view_desc.create_update_view()
            if not view_desc.the_view:
                cls.write([view_desc], {'the_view': the_view})
        return view_descs

    @classmethod
    def write(cls, instances, values):
        super(XMLViewDesc, cls).write(instances, values)
        if 'the_view' in values:
            return
        for view_desc in instances:
            the_view = view_desc.create_update_view()
            if not view_desc.the_view:
                cls.write([view_desc], {'the_view': the_view})

    @classmethod
    def delete(cls, records):
        to_delete = [rec.the_view for rec in records if rec.the_view]
        super(XMLViewDesc, cls).delete(records)
        ModelData = Pool().get('ir.model.data')
        good_data = ModelData.search([
            ('module', '=', 'process'),
            ('model', '=', 'ir.ui.view'),
            ('db_id', 'in', [x.id for x in to_delete])])
        ModelData.delete(good_data)
        View = Pool().get('ir.ui.view')
        View.delete(to_delete)


class StepDesc(model.CoopSQL):
    'Step Desc'

    __metaclass__ = PoolMeta
    __name__ = 'process.step_desc'

    pyson = fields.Char('Pyson Constraint')
    custom_views = fields.One2Many(
        'coop_process.xml_view_desc',
        'for_step',
        'Custom Views',
        context={'for_step_name': Eval('technical_name', '')},
        states={'readonly': ~Eval('technical_name')},
    )
    main_model = fields.Many2One(
        'ir.model',
        'Main Model',
        states={'readonly': ~~Eval('main_model')},
        domain=[
            ('is_workflow', '=', True),
            ('model', '!=', 'process.process_framework')
        ],
    )

    def get_pyson_for_button(self):
        return self.pyson or ''

    def execute(self, target, execute_after=True):
        origin = target.current_state.step
        if execute_after:
            origin.execute_after(target)
        self.execute_before(target)
        target.set_state(self)


class ProcessParameters(model.CoopView):
    'Process Parameters'

    __name__ = 'coop_process.process_parameters'

    date = fields.Date('Date')
    model = fields.Many2One(
        'ir.model',
        'Model',
        domain=[('is_workflow', '=', 'True')],
        states={'readonly': True},
    )
    good_process = fields.Many2One(
        'process.process_desc',
        'Good Process',
        on_change_with=['date, model'],
        depends=['date', 'model'],
    )

    @classmethod
    def __setup__(cls):
        super(ProcessParameters, cls).__setup__()
        cls.good_process = copy.copy(cls.good_process)
        cls.good_process.domain = cls.build_process_domain()
        cls.good_process.depends = cls.build_process_depends()
        cls.good_process.on_change_with = cls.build_process_depends()

    @classmethod
    def build_process_domain(cls):
        return [
            ('on_model', '=', Eval('model')),
            utils.get_versioning_domain('date')]

    @classmethod
    def build_process_depends(cls):
        return ['model', 'date']

    @classmethod
    def default_date(cls):
        return utils.today()

    @classmethod
    def default_model(cls):
        raise NotImplementedError

    def on_change_with_good_process(self):
        try:
            good_process = utils.get_domain_instances(self, 'good_process')
            if not good_process or len(good_process) > 1:
                return None
            return good_process[0].id
        except Exception:
            return None


class ProcessFinder(Wizard):
    'Process Finder'

    class VoidStateAction(StateAction):
        def __init__(self):
            StateAction.__init__(self, None)

        def get_action(self):
            return None

    start_state = 'process_parameters'
    process_parameters = StateView(
        'coop_process.process_parameters',
        'coop_process.process_parameters_form',
        [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Start Process', 'action', 'tryton-go-next')])
    action = VoidStateAction()

    @classmethod
    def __setup__(cls):
        super(ProcessFinder, cls).__setup__()
        cls.process_parameters = copy.copy(cls.process_parameters)
        cls.process_parameters.model_name = cls.get_parameters_model()
        cls.process_parameters.view = cls.get_parameters_view()

    def do_action(self, action):
        ActWindow = Pool().get('ir.action.act_window')
        Action = Pool().get('ir.action')
        good_view = self.process_parameters.good_process.get_act_window()
        good_action = ActWindow(good_view)
        good_values = Action.get_action_values(
            'ir.action.act_window', [good_action.id])
        good_values[0]['views'] = [
            view for view in good_values[0]['views'] if view[1] == 'form']
        good_obj = self.instanciate_main_object()
        good_obj.save()
        return good_values[0], {
            'res_id': good_obj.id}

    def instanciate_main_object(self):
        GoodModel = Pool().get(self.process_parameters.model.model)
        good_obj = GoodModel()
        good_obj.current_state = \
            self.process_parameters.good_process.all_steps[0]
        return good_obj

    @classmethod
    def get_parameters_model(cls):
        return 'coop_process.process_parameters'

    @classmethod
    def get_parameters_view(cls):
        return 'coop_process.process_parameters_form'


class GenerateGraph():
    'Generate Graph'

    __metaclass__ = PoolMeta
    __name__ = 'process.graph_generation'

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

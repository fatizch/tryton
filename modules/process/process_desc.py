import pydot
import inspect

from trytond.model import ModelView, ModelSQL
from trytond.wizard import Wizard, StateAction
from trytond.report import Report
from trytond.transaction import Transaction
from trytond.pyson import Eval, Bool
from trytond.pool import Pool

from trytond.modules.coop_utils import coop_string
from trytond.modules.coop_utils import fields

__all__ = [
    'Status',
    'ProcessStepRelation',
    'ProcessMenuRelation',
    'Process',
    'TransitionAuthorization',
    'Code',
    'ProcessTransition',
    'ProcessStep',
    'StepGroupRelation',
    'GenerateGraph',
    'GenerateGraphWizard',
    ]


class Status(ModelSQL, ModelView):
    'Process Status'

    __name__ = 'process.status'

    name = fields.Char('Name', required=True, translate=True)
    code = fields.Char('Code', required=True)
    relations = fields.One2Many('process-process.step', 'status', 'Relations',
        states={'readonly': True})


class ProcessStepRelation(ModelSQL, ModelView):
    'Process to Step relation'

    __name__ = 'process-process.step'

    process = fields.Many2One('process', 'Process', ondelete='CASCADE')
    step = fields.Many2One('process.step', 'Step', ondelete='RESTRICT')
    status = fields.Many2One('process.status', 'Status', ondelete='RESTRICT')
    order = fields.Integer('Order')

    def get_rec_name(self, name):
        res = ''
        if self.process:
            res += '%s - ' % self.process.rec_name
        if self.step:
            res += self.step.rec_name
        if self.status:
            res += ' (%s)' % self.status.rec_name
        if not res:
            res = super(ProcessStepRelation, self).get_rec_name(name)
        return res


class ProcessMenuRelation(ModelSQL):
    'Process Menu Relation'

    __name__ = 'process-menu'

    process = fields.Many2One('process', 'Process', ondelete='CASCADE')
    menu = fields.Many2One('ir.ui.menu', 'Menu', ondelete='RESTRICT')


class Process(ModelSQL, ModelView):
    'Process'

    __name__ = 'process'

    technical_name = fields.Char('Technical Name', required=True,
        on_change_with=['fancy_name', 'technical_name'])
    fancy_name = fields.Char('Name', translate=True)
    on_model = fields.Many2One('ir.model', 'On Model',
        # This model must be workflow compatible
        domain=[('is_workflow', '=', True),
            ('model', '!=', 'process.process_framework')],
        required=True)
    all_steps = fields.One2Many('process-process.step', 'process', 'All Steps',
        order=[('order', 'ASC')], states={
            'invisible': Bool(Eval('display_steps_without_status'))})
    display_steps_without_status = fields.Function(
        fields.Boolean('Display Steps Without Status'),
        'get_display_steps_without_status', 'set_void')
    steps_to_display = fields.Many2Many('process-process.step', 'process',
        'step', 'Steps', states={
            'invisible': Bool(~Eval('display_steps_without_status'))})
    transitions = fields.One2Many('process.transition', 'on_process',
        'Transitions')
    xml_header = fields.Text('Header XML')
    xml_footer = fields.Text('Footer XML')
    xml_tree = fields.Text('Tree View XML')
    step_button_group_position = fields.Selection([
            ('', 'None'), ('right', 'Right'), ('bottom', 'Bottom')],
        'Process Overview Positioning')
    menu_items = fields.Many2Many('process-menu', 'process', 'menu', 'Menus')
    menu_icon = fields.Selection('list_icons', 'Menu Icon')
    menu_name = fields.Char('Menu name', on_change_with=[
            'fancy_name', 'menu_name'])

    @classmethod
    def __setup__(cls):
        super(Process, cls).__setup__()
        cls._buttons.update({
            'update_view': {'invisible': ~Eval('id')}})
        cls._sql_constraints += [(
                'unique_tech_name', 'UNIQUE(technical_name)',
                'The technical name must be unique')]
        cls._error_messages.update({
                'use_steps_only_once':
                '%s: Step %s cannot be used more than once',
                })

    @classmethod
    def validate(cls, processes):
        super(Process, cls).validate(processes)
        for process in processes:
            used_steps = set()
            for relation in process.all_steps:
                if relation.step.id in used_steps:
                    cls.raise_user_error('use_steps_only_once', (
                            process.fancy_name, relation.step.technical_name))
                used_steps.add(relation.step.id)

    @classmethod
    def default_step_button_group_position(cls):
        return 'right'

    @classmethod
    def default_menu_icon(cls):
        Menu = Pool().get('ir.ui.menu')
        return Menu.default_icon()

    @classmethod
    def list_icons(cls):
        Menu = Pool().get('ir.ui.menu')
        return Menu.list_icons()

    def on_change_with_menu_name(self):
        if not (hasattr(self, 'fancy_name') and self.fancy_name):
            if (hasattr(self, 'menu_name') and self.menu_name):
                return self.menu_name
        else:
            return self.fancy_name

    @classmethod
    @ModelView.button
    def update_view(cls, processes):
        # This button is just used to trigger the update process of the view
        # associated to the process
        with Transaction().set_user(0):
            for process in processes:
                if isinstance(process, int):
                    process = cls(process)
                good_menus = process.create_update_menu_entry()
                if good_menus:
                    process.menu_items = good_menus
                    process.save()

    def get_all_steps(self):
        for elem in self.all_steps:
            yield elem.step

    def calculate_buttons_for_step(self, step_relation):
        result = {}
        for idx in range(len(self.all_steps)):
            cur_step = self.all_steps[idx].step
            for trans in self.transitions:
                if trans.from_step == step_relation.step and \
                        trans.to_step == cur_step:
                    result[cur_step.id] = ('trans', trans)
                    break
            if not cur_step.id in result:
                result[cur_step.id] = ('step', cur_step)
        for trans in self.transitions:
            if (trans.from_step == step_relation.step and
                    trans.kind == 'complete'):
                result['complete'] = trans
                break
        return result

    def get_or_create_root_menu_for_lang(self, lang):
        ModelData = Pool().get('ir.model.data')
        good_model, = ModelData.search([
                ('module', '=', 'process'),
                ('fs_id', '=', 'menu_process_lang')])
        Menu = Pool().get('ir.ui.menu')
        lang_menu = Menu.search([
                ('name', '=', lang.code),
                ('parent', '=', good_model.db_id)])
        if not lang_menu:
            lang_menu = Menu()
            lang_menu.name = lang.code
            lang_menu.parent = good_model.db_id
            lang_menu.save()
            return lang_menu
        else:
            return lang_menu[0]

    def create_or_update_menu(self, good_action, lang):
        MenuItem = Pool().get('ir.ui.menu')
        good_menu = MenuItem.search([
                ('name', '=', '%s_%s' % (self.technical_name, lang.code))])
        good_menu = good_menu[0] if good_menu else MenuItem()
        good_menu.parent = self.get_or_create_root_menu_for_lang(lang)
        good_menu.name = '%s_%s' % (self.technical_name, lang.code)
        good_menu.sequence = 10
        good_menu.action = good_action
        good_menu.icon = self.menu_icon
        good_menu.save()
        return good_menu

    def create_or_update_action(self, lang):
        ActWin = Pool().get('ir.action.act_window')
        good_action = None
        if (hasattr(self, 'menu_items') and self.menu_items):
            for menu in self.menu_items:
                if not menu.name == '%s_%s' % (self.technical_name, lang.code):
                    continue
                if hasattr(menu, 'action') and menu.action:
                    good_action = menu.action
                    break
        if not good_action:
            good_action = ActWin()
        good_action.name = self.fancy_name
        good_action.res_model = self.on_model.model
        good_action.context = "{'running_process': '%s'}" % (
            self.technical_name)
        good_action.domain = "[('current_state', 'in', [%s])]" % (
            ','.join(map(lambda x: str(x.id), self.all_steps)))
        good_action.sequence = 10
        good_action.save()
        return good_action

    def get_xml_header(self, colspan="4"):
        xml = '<group name="process_header" colspan="%s">' % colspan
        if hasattr(self, 'xml_header') and self.xml_header:
            xml += self.xml_header
        xml += '</group>'
        xml += '<newline/>'
        # We need to have cur_state in the view so our Pyson Eval can work
        # properly
        xml += '<field name="current_state" invisible="1" '
        xml += 'readonly="1" colspan="4"/>'
        xml += '<newline/>'
        return xml

    def build_step_group_header(
            self, step_relation, group_name='group', col=4, yexp=True):
        step = step_relation.step
        step_pyson, auth_pyson = step.get_pyson_for_display(step_relation)
        xml = '<group name="%s_%s" ' % (group_name, step.technical_name)
        xml += 'xfill="1" xexpand="1"'
        if yexp:
            xml += ' yfill="1" yexpand="1" '
        else:
            xml += ' yfill="0" yexpand="0" '
        xml += 'states="{'
        xml += "'invisible': "
        if auth_pyson:
            xml += 'Not(And(%s, %s))' % (step_pyson, auth_pyson)
        else:
            xml += 'Not(%s)' % step_pyson
        xml += '}" col="%s">' % col
        return xml

    def build_step_auth_group_if_needed(self, step_relation):
        step = step_relation.step
        step_pyson, auth_pyson = step.get_pyson_for_display(step_relation)

        xml = ''
        if auth_pyson:
            xml += '<group name="group_%s_noauth" ' % step.technical_name
            xml += 'xfill="1" xexpand="1" yfill="1" yexpand="1" '
            xml += 'states="{'
            xml += "'invisible': Not(And(%s, Not(%s)))" % (
                step_pyson, auth_pyson)
            xml += '}">'
            xml += '<label id="noauth_text" string="The current record is '
            'in a state (%s) that you are not allowed to view."/>' % (
                step.fancy_name)
            xml += '</group>'
        return xml

    def build_step_buttons(self, step_relation):
        the_buttons = self.calculate_buttons_for_step(step_relation)
        nb_buttons = len(the_buttons)
        xml = ''
        for cur_relation in self.all_steps:
            the_step = cur_relation.step
            if cur_relation == step_relation:
                # The "current state" button
                xml += '<button string="%s %s" name="_button_current_%s"/>' % (
                    '==>', the_step.fancy_name, self.id)
                continue
            if the_buttons[the_step.id][0] == 'trans':
                xml += the_buttons[the_step.id][1].build_button()
                continue
            elif the_buttons[the_step.id][0] == 'step':
                xml += '<button string="%s" name="_button_step_%s_%s"/>' % (
                    the_step.fancy_name, self.id, the_step.id)
                continue
        if 'complete' in the_buttons:
            xml += the_buttons['complete'].build_button()
        return nb_buttons, xml

    def get_xml_for_steps(self):
        xml = ''
        for step_relation in self.all_steps:
            xml += '<newline/>'
            xml += self.build_step_group_header(
                step_relation, col=step_relation.step.colspan)
            xml += step_relation.step.calculate_form_view(self)
            xml += '</group>'
            xml += self.build_step_auth_group_if_needed(step_relation)
        xml += '<newline/>'
        return xml

    def get_finished_process_xml(self):
        xml = '<group name="group_tech_complete" '
        xml += 'xfill="1" xexpand="1" yfill="1" yexpand="1" '
        xml += 'states="{'
        xml += "'invisible': ~~Eval('current_state')"
        xml += '}">'
        xml += '<label id="complete_text" string="The current record '
        'completed the current process, please go ahead"/>'
        xml += '</group>'

        return xml

    def get_xml_for_buttons(self):
        xml = ''
        for step_relation in self.all_steps:
            xml += '<newline/>'
            nb_buttons, buttons_xml = self.build_step_buttons(step_relation)
            if self.step_button_group_position == 'right':
                xml += self.build_step_group_header(
                    step_relation, group_name='buttons', col=1, yexp=False)
            else:
                xml += self.build_step_group_header(
                    step_relation, group_name='buttons', col=nb_buttons)
            xml += buttons_xml
            xml += '</group>'
        return xml

    def get_xml_footer(self, colspan=4):
        xml = '<group name="process_footer" colspan="%s">' % colspan
        if hasattr(self, 'xml_footer') and self.xml_footer:
            xml += self.xml_footer
        xml += '</group>'

        return xml

    def build_xml_form_view(self):
        xml = '<?xml version="1.0"?>'
        xml += '<form string="%s" col="4">' % self.fancy_name
        xml += self.get_xml_header()
        xml += '<group name="process_content" '
        xml += 'xfill="1" xexpand="1" yfill="1" yexpand="1">'
        xml += self.get_xml_for_steps()
        xml += '<newline/>'
        xml += self.get_finished_process_xml()
        xml += '</group>'
        if self.step_button_group_position:
            if self.step_button_group_position == 'bottom':
                xml += '<newline/>'
            xml += '<group name="process_buttons" colspan="1" col="1" '
            if self.step_button_group_position == 'right':
                xml += 'xexpand="0" xfill="0" yexpand="1" yfill="1">'
            elif self.step_button_group_position == 'bottom':
                xml += 'xexpand="1" xfill="1" yexpand="0" yfill="0">'
            xml += self.get_xml_for_buttons()
            xml += '</group>'
        xml += '<newline/>'
        xml += self.get_xml_footer()
        xml += '</form>'
        return xml

    def build_xml_tree_view(self):
        xml = '<?xml version="1.0"?>'
        xml += '<tree string="%s">' % self.fancy_name
        xml += self.xml_tree
        xml += '</tree>'
        return xml

    def create_or_update_view(self, for_action, kind):
        if not kind in ('tree', 'form'):
            raise Exception
        ActView = Pool().get('ir.action.act_window.view')
        View = Pool().get('ir.ui.view')
        try:
            act_views = ActView.search([('act_window', '=', for_action)])
            act_view = None
            for act in act_views:
                if not act.view.type == kind:
                    continue
                act_view = act
                break
        except ValueError:
            act_view = None
        if not act_view:
            good_view = View()
            act_view = ActView()
        else:
            good_view = act_view.view
        good_view.model = self.on_model.model
        good_view.name = '%s_%s' % (self.technical_name, kind)
        good_view.type = kind
        #TODO: Which modules should be used here ?
        good_view.module = 'process'
        good_view.priority = 100
        if kind == 'tree':
            good_view.arch = self.build_xml_tree_view()
        elif kind == 'form':
            good_view.arch = self.build_xml_form_view()
        good_view.save()
        act_view.act_window = for_action
        act_view.sequence = 100
        act_view.view = good_view
        act_view.save()
        return act_view, good_view

    def create_update_menu_entry(self):
        # Views are calculated depending on the process' steps and a few other
        # things. In order to avoid runtime calculation, we store the views in
        # the database and provide access to them through a dedicated entry
        # point which is calculated, then can be modified / cloned.
        Lang = Pool().get('ir.lang')
        good_langs = Lang.search([('translatable', '=', True)])
        good_menus = []
        for lang in good_langs:
            good_action = self.create_or_update_action(lang)
            good_menus.append(self.create_or_update_menu(good_action, lang))
            with Transaction().set_context(language=lang.code):
                self.create_or_update_view(good_action, 'tree')
                self.create_or_update_view(good_action, 'form')
        return good_menus

    def get_step_relation(self, step):
        for elem in self.all_steps:
            if elem.step.id == step.id:
                return elem
        return None

    def get_first_state_relation(self):
        return self.all_steps[0]

    def first_step(self):
        return self.all_steps[0]

    def get_rec_name(self, name):
        return self.fancy_name

    def set_menu_item_list(self, previous_ids, new_ids):
        Menu = Pool().get('ir.ui.menu')
        Process = Pool().get('process')
        MenuItem = Pool().get('ir.ui.menu')
        ActWin = Pool().get('ir.action.act_window')
        View = Pool().get('ir.ui.view')
        to_delete = set(previous_ids) - set(new_ids)
        Process.write([self], {'menu_items': [('add', new_ids)]})
        menus = []
        act_wins = []
        views = []
        for menu in Menu.browse(to_delete):
            menus.append(menu)
            act_wins.append(menu.action)
            for view in menu.action.act_window_views:
                views.append(view.view)
        MenuItem.delete(menus)
        ActWin.delete(act_wins)
        View.delete(views)

    @classmethod
    def create(cls, values):
        processes = super(Process, cls).create(values)
        for process in processes:
            existing_menus = [x.id for x in process.menu_items]
            menus = process.create_update_menu_entry()
            menus_ids = [x.id for x in menus]
            process.set_menu_item_list(existing_menus, menus_ids)
        return processes

    @classmethod
    def write(cls, instances, values):
        # Each time we write the process, we update the view
        super(Process, cls).write(instances, values)
        if 'menu_items' in values:
            return
        for process in instances:
            existing_menus = [x.id for x in process.menu_items]
            menus = process.create_update_menu_entry()
            menus_ids = [x.id for x in menus]
            process.set_menu_item_list(existing_menus, menus_ids)

    @classmethod
    def delete(cls, processes):
        for process in processes:
            process.set_menu_item_list([x.id for x in process.menu_items], [])
        super(Process, cls).delete(processes)

    def get_act_window(self):
        if not self.menu_items:
            return None
        lang = Transaction().context.get('language')
        for menu in self.menu_items:
            if menu.name == '%s_%s' % (self.technical_name, lang):
                return menu.action

    def on_change_with_technical_name(self):
        if self.technical_name:
            return self.technical_name
        return coop_string.remove_blank_and_invalid_char(self.fancy_name)

    def get_display_steps_without_status(self, name):
        return False

    @classmethod
    def set_void(cls, instances, name, vals):
        pass


class TransitionAuthorization(ModelSQL):
    'Transition Authorization'

    __name__ = 'process.transition-group'

    transition = fields.Many2One('process.transition', 'Transition',
        ondelete='CASCADE')
    group = fields.Many2One('res.group', 'Group', ondelete='CASCADE')


class Code(ModelSQL, ModelView):
    'Code'

    __name__ = 'process.action'

    technical_kind = fields.Selection([
            ('step_before', 'Before'),
            ('step_after', 'After'),
            ('transition', 'Transition')],
        'Kind', states={'invisible': True})
    source_code = fields.Function(
        fields.Text('Source Code', on_change_with=['method_name', 'on_model']),
        'on_change_with_source_code')
    on_model = fields.Function(
        fields.Many2One('ir.model', 'On Model'),
        'get_on_model')
    method_name = fields.Char('Method Name', required=True)
    parent_step = fields.Many2One('process.step', 'Parent Step',
        ondelete='CASCADE')
    parent_transition = fields.Many2One('process.transition',
        'Parent Transition', ondelete='CASCADE')
    sequence = fields.Integer('Sequence', states={'invisible': True})

    @classmethod
    def __setup__(cls):
        super(Code, cls).__setup__()
        cls._error_messages.update({
                'non_matching_method': 'Method %s does not exist on model %s'})

    def pre_validate(self):
        if not (hasattr(self, 'on_model') and self.on_model):
            return
        if not (hasattr(self, 'method_name') and self.method_name):
            return
        TargetModel = Pool().get(self.on_model.model)
        if not (self.method_name in dir(TargetModel) and callable(
                    getattr(TargetModel, self.method_name))):
            self.raise_user_error('non_matching_method', (
                    self.method_name, self.on_model.get_rec_name(None)))

    def execute(self, target):
        if not target.__name__ == self.on_model.model:
            raise Exception('Bad models ! Expected %s got %s' % (
                    self.on_model.model, target.__name__))
        result = getattr(target, self.method_name)()
        if (not result or
                not isinstance(result, (list, tuple)) and result is True):
            return
        res, errs = result
        if not res or errs:
            target.raise_user_error(errs)

    def on_change_with_source_code(self, name=None):
        if not (hasattr(self, 'method_name') and self.method_name):
            return ''
        if not (hasattr(self, 'on_model') and self.on_model):
            return ''
        try:
            GoodModel = Pool().get(self.on_model.model)
            func = getattr(GoodModel, self.method_name)
            return ''.join(inspect.getsourcelines(func)[0])
        except:
            return 'Source Code unavailable'

    def get_on_model(self, name):
        if self.parent_step and self.parent_step.main_model:
            #TODO : to change from process module to coop_process
            return self.parent_step.main_model.id
        elif (self.parent_transition and self.parent_transition.on_process
                and self.parent_transition.on_process.on_model):
            return self.parent_transition.on_process.on_model.id


class ProcessTransition(ModelSQL, ModelView):
    'Step Transition'

    __name__ = 'process.transition'

    on_process = fields.Many2One('process', 'On Process', required=True,
        ondelete='CASCADE')
    from_step = fields.Many2One('process.step', 'From Step',
        ondelete='CASCADE', required=True)
    to_step = fields.Many2One('process.step', 'To Step', ondelete='CASCADE',
        domain=[('id', '!=', Eval('from_step'))], depends=['from_step'],
        states={'invisible': Eval('kind') != 'standard'})
    kind = fields.Selection([
            ('standard', 'Standard Transition'),
            ('complete', 'Complete Process')],
        'Transition Kind', required=True)
    # Could be useful if we need to find the dependencies of the pyson expr :
    #  re.compile('Eval\(\'([a-zA-Z0-9._]*)\'', re.I|re.U) + finditer
    pyson = fields.Char('Pyson Constraint')
    methods = fields.One2ManyDomain('process.action', 'parent_transition',
        'Methods', domain=[('technical_kind', '=', 'transition')],
        order=[('sequence', 'ASC')])
    method_kind = fields.Selection([
            ('replace', 'Replace Step Methods'),
            ('add', 'Executed between steps')],
        'Method Behaviour')
    authorizations = fields.Many2Many('process.transition-group', 'transition',
        'group', 'Authorizations')
    priority = fields.Integer('Priority')

    def execute(self, target):
        if (self.kind == 'standard' and self.is_forward() or
                self.kind == 'complete') and self.method_kind == 'add':
            self.from_step.execute_after(target)
        if self.methods:
            for method in self.methods:
                method.execute(target)
        if self.kind == 'standard' and self.is_forward and \
                self.method_kind == 'add':
            self.to_step.execute_before(target)
        if not self.kind == 'complete':
            target.set_state(self.to_step)
        else:
            target.set_state(None)

    @classmethod
    def default_method_kind(cls):
        return 'add'

    @classmethod
    def default_kind(cls):
        return 'standard'

    def build_button(self):
        if self.kind == 'complete':
            xml = '<button string="Complete" '
            xml += 'name="_button_transition_%s_%s"/>' % (
                self.on_process.id, self.id)
            return xml
        elif self.kind == 'standard':
            xml = '<button string="%s" name="_button_transition_%s_%s"/>' % (
                self.to_step.fancy_name, self.on_process.id, self.id)
            return xml
        else:
            raise NotImplementedError

    def get_rec_name(self, name):
        if not (hasattr(self, 'to_step') and self.to_step):
            if self.kind == 'complete':
                return 'Complete'
            return '...'
        return self.to_step.get_rec_name(name)

    @classmethod
    def default_methods(cls):
        return ''

    def is_forward(self):
        if (self.on_process.get_step_relation(self.from_step).order <
                self.on_process.get_step_relation(self.to_step).order):
            return True
        return False

    def get_pyson_authorizations(self):
        if not (hasattr(self, 'authorizations') and self.authorizations):
            return 'True'
        auth_ids = map(lambda x: x.id, self.authorizations)
        return "Eval('groups', []).contains(%s)" % auth_ids

    def get_pyson_readonly(self):
        pyson = None if not self.pyson else self.pyson
        if not self.pyson:
            pyson = None
        else:
            pyson = self.pyson
        return pyson


class StepGroupRelation(ModelSQL):
    'Step Group Relation'

    __name__ = 'process.step-group'

    step_desc = fields.Many2One('process.step', 'Process Step',
        ondelete='CASCADE')
    group = fields.Many2One('res.group', 'Group', ondelete='CASCADE')


class ProcessStep(ModelSQL, ModelView):
    'Process Step'

    __name__ = 'process.step'
    _rec_name = 'fancy_name'

    technical_name = fields.Char('Technical Name', on_change_with=[
            'technical_name', 'fancy_name'])
    fancy_name = fields.Char('Name', required=True, translate=True)
    step_xml = fields.Text('XML')
    authorizations = fields.Many2Many('process.step-group', 'step_desc',
        'group', 'Authorizations')
    code_before = fields.One2ManyDomain('process.action', 'parent_step',
        'Executed Before Step', domain=[
            ('technical_kind', '=', 'step_before')],
        order=[('sequence', 'ASC')])
    code_after = fields.One2ManyDomain('process.action', 'parent_step',
        'Executed After Step', domain=[('technical_kind', '=', 'step_after')],
        order=[('sequence', 'ASC')])
    colspan = fields.Integer('View columns', required=True)
    processes = fields.One2Many('process-process.step', 'step', 'Transitions')

    @classmethod
    def __setup__(cls):
        super(ProcessStep, cls).__setup__()
        cls._sql_constraints += [(
                'unique_tech_name', 'UNIQUE(technical_name)',
                'The technical name must be unique')]

    @classmethod
    def write(cls, steps, values):
        super(ProcessStep, cls).write(steps, values)
        ProcessStepRelation = Pool().get('process-process.step')
        processes = set()
        for step in steps:
            used_in = ProcessStepRelation.search([('step', '=', step)])
            processes |= set(map(lambda x: x.process.id, used_in))
        if not processes:
            return
        Process = Pool().get('process')
        for process in processes:
            Process(process).create_update_menu_entry()

    def execute_before(self, target):
        for code in self.code_before:
            code.execute(target)

    def execute_after(self, target):
        if 'after_executed' in Transaction().context:
            return
        for code in self.code_after:
            code.execute(target)

    def build_step_main_view(self, process):
        xml = ''.join(self.step_xml.split('\n'))
        return xml

    def get_pyson_for_display(self, step_relation):
        step_pyson = "(Eval('current_state', 0) == %s)" % (
            step_relation.id)
        if self.authorizations:
            auth_pyson = '('
            for elem in self.authorizations:
                auth_pyson += "Eval('groups', []).contains(%s) or " % elem.id
            auth_pyson = auth_pyson[:-4] + ')'
        else:
            auth_pyson = None
        return step_pyson, auth_pyson

    def calculate_form_view(self, process):
        xml = self.build_step_main_view(process)
        return xml

    def on_change_with_technical_name(self, name=None):
        if self.technical_name:
            return self.technical_name
        elif self.fancy_name:
            return coop_string.remove_blank_and_invalid_char(self.fancy_name)

    @classmethod
    def default_colspan(cls):
        return 4


class GenerateGraph(Report):
    __name__ = 'process.generate_graph.report'

    @classmethod
    def build_graph(cls, process):
        graph = pydot.Dot(fontsize="8")
        graph.set('center', '1')
        graph.set('ratio', 'auto')
        graph.set('splines', 'ortho')
        graph.set('fontname', 'Inconsolata')
        #graph.set('concentrate', '1')
        #graph.set('rankdir', 'LR')
        return graph

    @classmethod
    def build_step(cls, process, step, graph, nodes):
        nodes[step.id] = pydot.Node(step.fancy_name, style='filled',
            shape='rect', fontname='Century Gothic')
        # if not step.to_steps:
            # nodes[step.id].set('style', 'filled')
            # nodes[step.id].set('shape', 'circle')
            # nodes[step.id].set('fillcolor', '#a2daf4')

    @classmethod
    def build_transition(cls, process, step, transition, graph, nodes, edges):
        good_edge = pydot.Edge(nodes[transition.from_step.id],
            nodes[transition.to_step.id], fontname='Century Gothic')
        good_edge.set('len', '1.0')
        good_edge.set('constraint', '1')
        good_edge.set('weight', '1.0')
        edges[(step.id, transition.to_step.id)] = good_edge

    @classmethod
    def build_inverse_transition(cls, process, step, transition, graph, nodes,
            edges):
        tr_fr, tr_to = transition.from_step.id, transition.to_step.id
        if (tr_to, tr_fr) in edges:
            edges[(tr_to, tr_fr)].set('dir', 'both')
        else:
            good_edge = pydot.Edge(nodes[transition.from_step.id],
                nodes[transition.to_step.id], fontname='Century Gothic')
            good_edge.set('constraint', '0')
            good_edge.set('weight', '0.2')
            edges[(tr_fr, tr_to)] = good_edge

    @classmethod
    def build_complete_transition(cls, process, step, transition, graph, nodes,
            edges):
        nodes['tr%s' % transition.id] = pydot.Node('Complete', style='filled',
            shape='circle', fontname='Century Gothic', fillcolor='#ff0000')
        edges[(transition.from_step.id, 'tr%s' % transition.id)] = pydot.Edge(
            nodes[transition.from_step.id], nodes['tr%s' % transition.id],
            fontname='Century Gothic', len=1.0, constraint=1, weight=1.0)

    @classmethod
    def execute(cls, ids, data):
        pool = Pool()
        ActionReport = pool.get('ir.action.report')
        Process = pool.get('process')
        action_report_ids = ActionReport.search([
                ('report_name', '=', cls.__name__)])
        if not action_report_ids:
            raise Exception('Error', 'Report (%s) not find!' % cls.__name__)
        action_report = ActionReport(action_report_ids[0])
        the_process = Process(Transaction().context.get('active_id'))
        graph = cls.build_graph(the_process)
        nodes = {}
        for step in the_process.get_all_steps():
            cls.build_step(the_process, step, graph, nodes)
        edges = {}
        for transition in the_process.transitions:
            if transition.kind == 'standard' and transition.is_forward():
                cls.build_transition(the_process, step, transition, graph,
                    nodes, edges)
        for transition in the_process.transitions:
            if transition.kind == 'standard' and transition.is_forward():
                cls.build_inverse_transition(the_process, step, transition,
                    graph, nodes, edges)
        for transition in the_process.transitions:
            if transition.kind == 'complete':
                cls.build_complete_transition(the_process, step, transition,
                    graph, nodes, edges)
        nodes[the_process.first_step().id].set('style', 'filled')
        nodes[the_process.first_step().id].set('shape', 'octagon')
        nodes[the_process.first_step().id].set('fillcolor', '#0094d2')
        for node in nodes.itervalues():
            graph.add_node(node)
        for edge in edges.itervalues():
            graph.add_edge(edge)
        data = graph.create(prog='dot', format='pdf')
        return ('pdf', buffer(data), False, action_report.name)


class GenerateGraphWizard(Wizard):
    __name__ = 'process.generate_graph'

    start_state = 'print_'

    print_ = StateAction('process.report_generate_graph')

    def transition_print_(self):
        return 'end'

    def do_print_(self, action):
        return action, {'id': Transaction().context.get('active_id') }

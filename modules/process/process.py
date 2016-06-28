import lxml
import pydot
import inspect
import ast
import json
from unidecode import unidecode

from trytond.model import ModelView, ModelSQL, Unique
from trytond.wizard import Wizard, StateAction
from trytond.report import Report
from trytond.transaction import Transaction
from trytond.server_context import ServerContext
from trytond.pyson import Eval, Bool, Or, And, Not
from trytond.pool import Pool, PoolMeta

from trytond.modules.cog_utils import coop_string, utils
from trytond.modules.cog_utils import fields, model, export

__metaclass__ = PoolMeta
__all__ = [
    'Status',
    'ProcessStepRelation',
    'ProcessMenuRelation',
    'Process',
    'TransitionAuthorization',
    'ProcessAction',
    'ProcessTransition',
    'ProcessStep',
    'StepGroupRelation',
    'GenerateGraph',
    'GenerateGraphWizard',
    'ProcessActWindow',
    ]


class Status(ModelSQL, ModelView):
    'Process Status'

    __name__ = 'process.status'

    name = fields.Char('Name', required=True, translate=True)
    code = fields.Char('Code', required=True)
    relations = fields.One2Many('process-process.step', 'status', 'Relations',
        states={'readonly': True}, target_not_required=True,
        target_not_indexed=True)

    @fields.depends('code', 'name')
    def on_change_with_code(self):
        if self.code:
            return self.code
        return coop_string.slugify(self.name)


class ProcessStepRelation(export.ExportImportMixin, ModelSQL, ModelView):
    'Process to Step relation'

    __name__ = 'process-process.step'
    _func_key = 'technical_step_name'

    process = fields.Many2One('process', 'Process', ondelete='CASCADE',
        required=True, select=True)
    step = fields.Many2One('process.step', 'Step', ondelete='RESTRICT',
        required=True, select=True)
    status = fields.Many2One('process.status', 'Status', ondelete='RESTRICT')
    order = fields.Integer('Order')
    technical_step_name = fields.Function(fields.Char('Technical Step Name'),
        'get_technical_step_name', searcher='search_technical_step_name')

    def get_technical_step_name(self, name):
        return self.step.technical_name + '|' + self.process.technical_name

    @classmethod
    def search_technical_step_name(cls, name, clause):
        assert clause[1] == '='
        if '|' in clause[2]:
            operands = clause[2].split('|')
            if len(operands) == 2:
                step_name, process_name = clause[2].split('|')
                return [('step.technical_name', clause[1], step_name),
                    ('process.technical_name', clause[1], process_name)]
            else:
                return [('id', '=', None)]
        else:
            return ['OR',
                [('step.technical_name',) + tuple(clause[1:])],
                [('process.technical_name',) + tuple(clause[1:])],
                ]

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


class Process(ModelSQL, ModelView, model.TaggedMixin):
    'Process'

    __name__ = 'process'

    technical_name = fields.Char('Technical Name', required=True)
    fancy_name = fields.Char('Name', translate=True)
    on_model = fields.Many2One('ir.model', 'On Model',
        # This model must be workflow compatible
        domain=[('is_workflow', '=', True),
            ('model', '!=', 'process.process_framework')],
        required=True, ondelete='RESTRICT')
    all_steps = fields.One2Many('process-process.step', 'process', 'All Steps',
        order=[('order', 'ASC')], delete_missing=True, states={
            'invisible': Bool(Eval('display_steps_without_status'))})
    display_steps_without_status = fields.Function(
        fields.Boolean('Display Steps Without Status'),
        'get_display_steps_without_status', 'set_void')
    steps_to_display = fields.Many2Many('process-process.step', 'process',
        'step', 'Steps', states={
            'invisible': Bool(~Eval('display_steps_without_status'))})
    transitions = fields.One2Many('process.transition', 'on_process',
        'Transitions', delete_missing=True)
    xml_header = fields.Text('Header XML')
    xml_footer = fields.Text('Footer XML')
    xml_tree = fields.Text('Tree View XML', required=True)
    step_button_group_position = fields.Selection([
            ('', 'None'), ('right', 'Right'), ('bottom', 'Bottom')],
        'Process Overview Positioning')
    menu_items = fields.Many2Many('process-menu', 'process', 'menu', 'Menus')
    menu_icon = fields.Selection('list_icons', 'Menu Icon')
    menu_name = fields.Char('Menu name')
    action_windows = fields.One2Many('process.process-act_window',
        'process', 'Action Windows', delete_missing=True)
    end_step_name = fields.Char('End Step Name')

    @classmethod
    def __setup__(cls):
        super(Process, cls).__setup__()
        cls._buttons.update({
            'update_view': {'invisible': ~Eval('id')}})
        t = cls.__table__()
        cls._sql_constraints += [(
                'unique_tech_name', Unique(t, t.technical_name),
                'The technical name must be unique')]
        cls._error_messages.update({
                'use_steps_only_once':
                '%s: Step %s cannot be used more than once',
                'not_allowed_message': 'The current record is in a state '
                '(%s) that you are not allowed to view',
                'process_completed': 'The current record completed the '
                'current process, please go ahead',
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
    def default_xml_tree(cls):
        return '<field name="current_state"/>'

    @classmethod
    def list_icons(cls):
        Menu = Pool().get('ir.ui.menu')
        return Menu.list_icons()

    @fields.depends('fancy_name', 'menu_name')
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
            if cur_step.id not in result:
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
        pool = Pool()
        ActWin = pool.get('ir.action.act_window')
        ProcessActWindow = pool.get('process.process-act_window')

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
        good_action.context = json.dumps(self.get_action_context())
        good_action.domain = '[["current_state", "in", [%s]]]' % (
            ','.join(map(lambda x: str(x.id), self.all_steps)))
        good_action.sequence = 10
        good_action.save()

        existing = [x for x in self.action_windows if
            x.action_window == good_action and x.language == lang]

        if existing:
            return good_action

        new_relation = ProcessActWindow()
        new_relation.process = self
        new_relation.language = lang
        new_relation.action_window = good_action
        new_relation.save()

        return good_action

    def get_action_context(self):
        return {"running_process": "%s" % self.technical_name}

    def get_xml_header(self, colspan="4"):
        xml = ''
        if hasattr(self, 'xml_header') and self.xml_header:
            xml += ('<group id="process_header" colspan="%s" string="">'
                % colspan)
            xml += self.xml_header
            xml += '</group>'
            xml += '<newline/>'
        # We need to have cur_state in the view so our Pyson Eval can work
        # properly
        xml += '<field name="current_state" invisible="1" '
        xml += 'readonly="1" colspan="4"/>'
        xml += '<newline/>'
        return xml

    def build_step_group_header(self, step_relation, group_name='group',
            col=4, yexp=True, string=None):
        step = step_relation.step
        step_pyson, auth_pyson = step.get_pyson_for_display(step_relation)
        xml = '<group id="%s_%s" ' % (group_name, step.technical_name)
        xml += 'xfill="1" xexpand="1"'
        if yexp:
            xml += ' yfill="1" yexpand="1" '
        else:
            xml += ' yfill="0" yexpand="0" '
        xml += 'states="{'
        xml += "&quot;invisible&quot;: "
        if auth_pyson:
            pyson = Not(And(step_pyson, auth_pyson))
            invisible_def = utils.get_json_from_pyson(pyson)
        else:
            pyson = Not(step_pyson)
            invisible_def = utils.get_json_from_pyson(pyson)
        xml += '%s' % invisible_def
        xml += '}" col="%s"' % col
        if string:
            xml += ' string="%s"' % string
        xml += '>'
        return xml

    def build_step_auth_group_if_needed(self, step_relation):
        step = step_relation.step
        step_pyson, auth_pyson = step.get_pyson_for_display(step_relation)

        pyson = Not(And(step_pyson, Not(auth_pyson or Bool(True))))
        invisible_def = utils.get_json_from_pyson(pyson)

        xml = ''
        if auth_pyson:
            xml += '<newline/>'
            xml += '<group id="group_%s_noauth" ' % step.technical_name
            xml += 'yfill="1" yexpand="1" '
            xml += 'states="{'
            xml += "&quot;invisible&quot;: %s" % invisible_def
            xml += '}">'
            xml += '<label id="noauth_text" string="%s"/>' % (
                self.raise_user_error('not_allowed_message',
                    (step.fancy_name,), raise_exception=False))
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
                xml += '<button string="%s" name="_button_current_%s"' % (
                    the_step.fancy_name, self.id)
                xml += ' icon="tryton-go-next"/>'
                continue
            if the_buttons[the_step.id][0] == 'trans':
                xml += the_buttons[the_step.id][1].build_button()
                continue
            elif the_buttons[the_step.id][0] == 'step':
                xml += '<button string="%s" name="_button_step_%s_%s_%s"/>' % (
                    the_step.fancy_name, self.id, step_relation.step.id,
                    the_step.id)
                continue
        if 'complete' in the_buttons:
            xml += the_buttons['complete'].build_button()
        return nb_buttons, xml

    def get_xml_for_steps(self):
        xml = ''
        for step_relation in self.all_steps:
            xml += '<newline/>'
            xml += self.build_step_group_header(
                step_relation, col=step_relation.step.colspan, string="")
            xml += step_relation.step.calculate_form_view(self)
            xml += '</group>'
            xml += self.build_step_auth_group_if_needed(step_relation)
        xml += '<newline/>'
        return xml

    def get_finished_process_xml(self):
        pyson = Bool(Eval('current_state'))
        invisible_def = utils.get_json_from_pyson(pyson)
        xml = '<group id="group_tech_complete" '
        xml += 'xfill="1" xexpand="1" yfill="1" yexpand="1" '
        xml += 'states="{'
        xml += "&quot;invisible&quot;: %s" % invisible_def
        xml += '}">'
        xml += '<label id="complete_text" string="%s"/>' % (
            self.raise_user_error('process_completed', raise_exception=False))
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
        xml = ''
        if hasattr(self, 'xml_footer') and self.xml_footer:
            xml = ('<group id="process_footer" colspan="%s" string="">'
                % colspan)
            xml += self.xml_footer
            xml += '</group>'

        return xml

    def build_xml_form_view(self):
        xml = '<?xml version="1.0"?>'
        xml += '<form string="%s" col="4">' % self.fancy_name
        xml += '<group id="process_content" '
        xml += 'xfill="1" xexpand="1" yfill="1" yexpand="1">'
        xml += self.get_xml_header()
        xml += self.get_xml_for_steps()
        xml += '<newline/>'
        xml += self.get_finished_process_xml()
        xml += '</group>'
        if self.step_button_group_position:
            if self.step_button_group_position == 'bottom':
                xml += '<newline/>'
            xml += '<group id="process_buttons" colspan="1" col="1" '
            if self.step_button_group_position == 'right':
                xml += 'xexpand="0" xfill="0" yexpand="1" yfill="1">'
            elif self.step_button_group_position == 'bottom':
                xml += 'xexpand="1" xfill="1" yexpand="0" yfill="0">'
            xml += self.get_xml_for_buttons()
            xml += '</group>'
        xml += '<newline/>'
        xml += self.get_xml_footer()
        xml += '</form>'
        # Prettify xml to ease reading
        return lxml.etree.tostring(lxml.etree.fromstring(xml),
            pretty_print=True)

    def build_xml_tree_view(self):
        xml = '<?xml version="1.0"?>'
        xml += '<tree string="%s">' % self.fancy_name
        xml += self.xml_tree
        xml += '</tree>'
        return xml

    def create_or_update_view(self, for_action, kind):
        if kind not in ('tree', 'form'):
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
        good_view.module = 'process_views'
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
        good_langs = Lang.search(['OR',
                ('translatable', '=', True),
                ('code', '=', 'en_US'),
                ])
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
    def write(cls, *args):
        # Each time we write the process, we update the view
        super(Process, cls).write(*args)
        actions = iter(args)
        for instances, values in zip(actions, actions):
            if 'menu_items' in values:
                continue
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
        action, = [x.action_window for x in self.action_windows if
            x.language.code == lang]
        return action

    @fields.depends('fancy_name', 'technical_name')
    def on_change_with_technical_name(self):
        if self.technical_name:
            return self.technical_name
        return coop_string.slugify(self.fancy_name)

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


class ProcessAction(ModelSQL, ModelView):
    'Process Action'

    __name__ = 'process.action'

    technical_kind = fields.Selection([
            ('step_before', 'Before'),
            ('step_after', 'After'),
            ('transition', 'Transition')],
        'Kind', states={'invisible': True})
    content = fields.Selection([
            ('method', 'Method'),
            ], 'Content')
    source_code = fields.Function(
        fields.Text('Source Code', states={
                'invisible': Eval('content', '') != 'method'},
            depends=['content']),
        'on_change_with_source_code')
    on_model = fields.Function(
        fields.Many2One('ir.model', 'On Model', states={
                'invisible': Eval('content', '') != 'method'},
            depends=['content']),
        'get_on_model')
    method_name = fields.Char('Method Name', states={
            'required': Eval('content', '') == 'method',
            'invisible': Eval('content', '') != 'method'},
        depends=['content'])
    parent_step = fields.Many2One('process.step', 'Parent Step',
        ondelete='CASCADE', select=True)
    parent_transition = fields.Many2One('process.transition',
        'Parent Transition', ondelete='CASCADE', select=True)
    sequence = fields.Integer('Sequence', states={'invisible': True})
    parameters = fields.Char('Parameters',
        states={'invisible': Eval('content', '') != 'method'},
        depends=['content'], help='Write parameters separated by ","')
    exec_rec_name = fields.Function(
        fields.Char('Execution Name'),
        'on_change_with_exec_rec_name')
    exec_parameters = fields.Function(
        fields.Char('Execution Parameters'),
        'on_change_with_exec_parameters')

    @classmethod
    def __setup__(cls):
        super(ProcessAction, cls).__setup__()
        cls._error_messages.update({
                'non_matching_method': 'Method %s does not exist on model %s',
                'source_code_unavailable': 'Source Code Unavailable',
                })

    @classmethod
    def default_content(cls):
        return 'method'

    @fields.depends('method_name', 'on_model')
    def pre_validate(self):
        if not self.on_model:
            return
        if not self.method_name:
            return
        TargetModel = Pool().get(self.on_model.model)
        if not (self.method_name in dir(TargetModel) and callable(
                    getattr(TargetModel, self.method_name))):
            self.raise_user_error('non_matching_method', (
                    self.method_name, self.on_model.get_rec_name(None)))

    def execute(self, target):
        def call_method(method, target, parameters=None):
            if parameters:
                parameters = ast.literal_eval('(%s,)' % parameters)
                result = method(target, *parameters)
            else:
                result = method(target)
            return result

        if self.content != 'method':
            raise NotImplementedError
        if not target.__name__ == self.on_model.model:
            raise Exception('Bad models ! Expected %s got %s' % (
                    self.on_model.model, target.__name__))
        # Test if classmethod or not
        method = getattr(target.__class__, self.method_name)
        if not hasattr(method, 'im_self') or method.im_self:
            target = [target]
        result = call_method(method, target, self.parameters)
        if (not result or
                not isinstance(result, (list, tuple)) and result is True):
            return
        res, errs = result
        if not res or errs:
            target.raise_user_error(errs)

    @fields.depends('parameters')
    def on_change_with_exec_parameters(self, name=None):
        return self.parameters

    @fields.depends('method_name')
    def on_change_with_exec_rec_name(self, name=None):
        return self.method_name

    @fields.depends('method_name', 'on_model')
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
            return self.raise_user_error('source_code_unavailable',
                raise_exception=False)

    def get_on_model(self, name):
        if self.parent_step and self.parent_step.main_model:
            # TODO : to change from process module to coop_process
            return self.parent_step.main_model.id
        elif (self.parent_transition and self.parent_transition.on_process and
                self.parent_transition.on_process.on_model):
            return self.parent_transition.on_process.on_model.id


class ProcessTransition(ModelSQL, ModelView):
    'Step Transition'

    __name__ = 'process.transition'

    on_process = fields.Many2One('process', 'On Process', required=True,
        ondelete='CASCADE', select=True)
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
        order=[('sequence', 'ASC')], target_not_required=True)
    method_kind = fields.Selection([
            ('replace', 'Replace Step Methods'),
            ('add', 'Executed between steps')],
        'Method Behaviour')
    authorizations = fields.Many2Many('process.transition-group', 'transition',
        'group', 'Authorizations')
    priority = fields.Integer('Priority')

    @classmethod
    def __setup__(cls):
        super(ProcessTransition, cls).__setup__()
        cls._error_messages.update({
                'complete_button_label': 'Complete',
                })

    @classmethod
    def view_attributes(cls):
        return super(ProcessTransition, cls).view_attributes() + [
            ('group[@id="methods"]', 'states',
                {'invisible': Eval('kind') != 'standard'}),
            ]

    def execute(self, target):
        result = None
        if (self.kind == 'standard' and self.is_forward() or
                self.kind == 'complete') and self.method_kind == 'add':
            result = self.from_step.execute_after(target)
        if self.methods:
            for method in self.methods:
                method.execute(target)
        if self.kind == 'standard' and self.is_forward() and \
                self.method_kind == 'add':
            result = (self.to_step.execute_before(target)
                if not result else result)
        if not self.kind == 'complete':
            target.set_state(
                self.to_step, target.current_state.process.technical_name)
        else:
            target.set_state(None)
            if not result:
                result = 'close'
        return result

    @classmethod
    def default_method_kind(cls):
        return 'add'

    @classmethod
    def default_kind(cls):
        return 'standard'

    def build_button(self):
        if self.kind == 'complete':
            complete_name = self.on_process.end_step_name or 'Complete'
            xml = '<button string="%s" ' % complete_name
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
                return self.raise_user_error('complete_button_label',
                    raise_exception=False)
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


class ProcessStep(ModelSQL, ModelView, model.TaggedMixin):
    'Process Step'

    __name__ = 'process.step'
    _rec_name = 'fancy_name'

    technical_name = fields.Char('Technical Name')
    fancy_name = fields.Char('Name', required=True, translate=True)
    step_xml = fields.Text('XML')
    authorizations = fields.Many2Many('process.step-group', 'step_desc',
        'group', 'Authorizations')
    code_before = fields.One2ManyDomain('process.action', 'parent_step',
        'Executed Before Step', domain=[
            ('technical_kind', '=', 'step_before')],
        order=[('sequence', 'ASC')], target_not_required=True)
    code_after = fields.One2ManyDomain('process.action', 'parent_step',
        'Executed After Step', domain=[('technical_kind', '=', 'step_after')],
        order=[('sequence', 'ASC')], target_not_required=True)
    colspan = fields.Integer('View columns', required=True)
    processes = fields.One2Many('process-process.step', 'step', 'Transitions',
        delete_missing=True)
    entering_wizard = fields.Many2One('ir.action', 'Entering Wizard', domain=[
            ('type', '=', 'ir.action.wizard')], ondelete='RESTRICT')
    exiting_wizard = fields.Many2One('ir.action', 'Exiting Wizard', domain=[
            ('type', '=', 'ir.action.wizard')], ondelete='RESTRICT')

    @classmethod
    def __setup__(cls):
        super(ProcessStep, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [(
                'unique_tech_name', Unique(t, t.technical_name),
                'The technical name must be unique')]

    @classmethod
    def write(cls, *args):
        super(ProcessStep, cls).write(*args)
        ProcessStepRelation = Pool().get('process-process.step')
        processes = set()
        actions = iter(args)
        for steps, values in zip(actions, actions):
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
        if self.entering_wizard:
            return self.entering_wizard.id

    def execute_after(self, target):
        if ServerContext().get('after_executed', None) is None:
            for code in self.code_after:
                code.execute(target)
        if self.exiting_wizard:
            return self.exiting_wizard.id

    def build_step_main_view(self, process):
        xml = ''.join((self.step_xml or '').split('\n'))
        return xml

    def get_pyson_for_display(self, step_relation):
        step_pyson = Bool(Eval('current_state', 0) == step_relation.id)
        if self.authorizations:
            auths = []
            for elem in self.authorizations:
                auths.append(Bool(Eval('groups', []).contains(elem.id)))
            auth_pyson = Or(*auths) if len(auths) > 1 else auths[0]
        else:
            auth_pyson = None
        return step_pyson, auth_pyson

    def calculate_form_view(self, process):
        xml = self.build_step_main_view(process)
        return xml

    @fields.depends('technical_name', 'fancy_name')
    def on_change_with_technical_name(self, name=None):
        if self.technical_name:
            return self.technical_name
        elif self.fancy_name:
            return coop_string.slugify(self.fancy_name)

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
        # graph.set('concentrate', '1')
        # graph.set('rankdir', 'LR')
        return graph

    @classmethod
    def build_step(cls, process, step, graph, nodes):
        name = unicode(unidecode(step.fancy_name))
        nodes[step.id] = pydot.Node(name, style='filled', shape='rect',
            fontname='Century Gothic')

    @classmethod
    def build_transition(cls, process, transition, graph, nodes, edges):
        good_edge = pydot.Edge(nodes[transition.from_step.id],
            nodes[transition.to_step.id], fontname='Century Gothic')
        good_edge.set('len', '1.0')
        good_edge.set('constraint', '1')
        good_edge.set('weight', '1.0')
        edges[(transition.from_step.id, transition.to_step.id)] = good_edge

    @classmethod
    def build_inverse_transition(cls, process, transition, graph, nodes,
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
    def build_complete_transition(cls, process, transition, graph, nodes,
            edges):
        nodes['tr%s' % transition.id] = pydot.Node('Complete', style='filled',
            shape='circle', fontname='Century Gothic', fillcolor='#ff0000')
        edges[(transition.from_step.id, 'tr%s' % transition.id)] = pydot.Edge(
            nodes[transition.from_step.id], nodes['tr%s' % transition.id],
            fontname='Century Gothic', len=1.0, constraint=1, weight=1.0)

    @classmethod
    def build_edges(cls, process, graph, nodes):
        edges = {}
        for transition in process.transitions:
            if transition.kind == 'standard' and transition.is_forward():
                cls.build_transition(process, transition, graph,
                    nodes, edges)
        for transition in process.transitions:
            if transition.kind == 'standard' and transition.is_forward():
                cls.build_inverse_transition(process, transition,
                    graph, nodes, edges)
        for transition in process.transitions:
            if transition.kind == 'complete':
                cls.build_complete_transition(process, transition,
                    graph, nodes, edges)
        return edges

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
        the_process = Process(data['id'])
        graph = cls.build_graph(the_process)
        nodes = {}
        for step in the_process.get_all_steps():
            cls.build_step(the_process, step, graph, nodes)
        edges = cls.build_edges(the_process, graph, nodes)

        nodes[the_process.first_step().step.id].set('style', 'filled')
        nodes[the_process.first_step().step.id].set('shape', 'octagon')
        nodes[the_process.first_step().step.id].set('fillcolor', '#0094d2')
        for node in nodes.itervalues():
            graph.add_node(node)
        for edge in edges.itervalues():
            graph.add_edge(edge)
        data = graph.create(prog='dot', format='pdf')
        return ('pdf', bytearray(data), False, action_report.name)


class GenerateGraphWizard(Wizard):
    __name__ = 'process.generate_graph'

    start_state = 'print_'

    print_ = StateAction('process.report_generate_graph')

    def transition_print_(self):
        return 'end'

    def do_print_(self, action):
        return action, {'id': Transaction().context.get('active_id')}


class ProcessActWindow(model.CoopSQL):
    'Process to Action Window Relation'

    __name__ = 'process.process-act_window'

    process = fields.Many2One('process', 'Process', ondelete='CASCADE',
        required=True, select=True)
    action_window = fields.Many2One('ir.action.act_window', 'Action Window',
        ondelete='CASCADE', required=True)
    language = fields.Many2One('ir.lang', 'Language', ondelete='RESTRICT')

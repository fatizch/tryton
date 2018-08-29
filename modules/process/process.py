# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import lxml
import pydot
import inspect
import ast
import json
from unidecode import unidecode

from sql import Literal, Table

from trytond import backend
from trytond.model import ModelView, ModelSQL, Unique
from trytond.wizard import Wizard, StateAction
from trytond.report import Report
from trytond.transaction import Transaction
from trytond.server_context import ServerContext
from trytond.pyson import Eval, Bool, Or, And, Not, In, Get
from trytond.pool import Pool

from trytond.modules.coog_core import coog_string, utils
from trytond.modules.coog_core import fields, model, export

__all__ = [
    'Status',
    'ProcessStepRelation',
    'Process',
    'TransitionAuthorization',
    'ProcessAction',
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
        states={'readonly': True}, target_not_required=True,
        target_not_indexed=True)

    @fields.depends('code', 'name')
    def on_change_with_code(self):
        if self.code:
            return self.code
        return coog_string.slugify(self.name)


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
        if self.status:
            return self.status.rec_name
        res = ''
        if self.process:
            res += '%s - ' % self.process.rec_name
        if self.step:
            res += self.step.rec_name
        if not res:
            res = super(ProcessStepRelation, self).get_rec_name(name)
        return res

    @classmethod
    def search_rec_name(cls, name, clause):
        assert clause[1] in ('=', 'like', 'ilike')
        return ['OR',
                [('step.fancy_name',) + tuple(clause[1:])],
                [('status', '!=', None),
                    ('status.name',) + tuple(clause[1:])],
                [('process.fancy_name',) + tuple(clause[1:])],
                ]

    @classmethod
    def delete(cls, relations):
        pool = Pool()
        Lang = pool.get('ir.lang')
        View = pool.get('ir.ui.view')
        languages = Lang.search(['OR',
                ('translatable', '=', True),
                ('code', '=', 'en'),
                ])

        def get_view_name(x):
            names = []
            for lang in languages:
                names.append('process_view_%s_%s' % (x.id, lang.code))
            return names

        view_names = map(get_view_name, relations)
        views = View.search(
            [('name', 'in', [x for names in view_names for x in names])])
        View.delete(views)
        super(ProcessStepRelation, cls).delete(relations)

    @classmethod
    def create(cls, values):
        instances = super(ProcessStepRelation, cls).create(values)
        for process in list({x.process for x in instances}):
            process.refresh_views()
        return instances

    @classmethod
    def write(cls, *args):
        # Each time we write the process, we update the view
        super(ProcessStepRelation, cls).write(*args)
        for process in list({x.process for x in sum(args[::2], [])}):
            process.refresh_views()


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
    menu_icon = fields.Selection('list_icons', 'Menu Icon')
    menu_name = fields.Char('Menu name')
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
    def __register__(cls, module_name):
        super(Process, cls).__register__(module_name)
        TableHandler = backend.get('TableHandler')
        # Migrate from 1.12 : Remove process generated menus
        if TableHandler.table_exist('process-menu'):
            cursor = Transaction().connection.cursor()
            menu = Table('ir_ui_menu')
            process_menu = Table('process-menu')
            cursor.execute(*process_menu.select(process_menu.menu))
            menu_ids = [r[0] for r in cursor.fetchall()]
            TableHandler.drop_table('process-menu', 'process-menu')
            if menu_ids:
                cursor.execute(*menu.delete(
                        where=(menu.id.in_(menu_ids))))

            action_table = Table('process_process-act_window')
            view = Table('ir_ui_view')
            act_window = Table('ir_action_act_window')
            act_window_view = Table('ir_action_act_window_view')
            query_table = action_table.join(act_window_view,
                condition=(
                    action_table.action_window == act_window_view.act_window))
            cursor.execute(
                *query_table.select(
                    act_window_view.act_window, act_window_view.view))

            ids = [r[0] for r in cursor.fetchall()]
            if ids:
                cursor.execute(*act_window.delete(
                        where=(act_window.id.in_(ids))))
            cursor.execute(*view.delete(where=(view.module == 'process_views')))

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
    def copy(cls, processes, default=None):
        default = {} if default is None else default
        default['steps_to_display'] = []
        return super(Process, cls).copy(processes, default)

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

    def init_new_process(self, instance):
        for elem in self.transitions:
            if elem.kind != 'start':
                continue
            if elem.to_step != instance.current_state.step:
                continue
            elem.execute(instance)

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
                process.refresh_views()

    def get_all_steps(self):
        for elem in self.all_steps:
            yield elem.step

    def get_action_context(self):
        return {'running_process': '%s' % self.technical_name}

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
        complete_buttons = []
        for trans in self.transitions:
            if (trans.from_step == step_relation.step and
                    trans.kind == 'complete'):
                complete_buttons.append(trans)
        if complete_buttons:
            result['complete'] = complete_buttons
        return result

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
        for button in the_buttons.get('complete', []):
            xml += button.build_button()
        return nb_buttons, xml

    def get_xml_for_step(self, step):
        xml = ''
        xml += '<newline/>'
        xml += self.build_step_group_header(
            step, col=step.step.colspan, string='')
        xml += step.step.calculate_form_view(self)
        xml += '</group>'
        xml += self.build_step_auth_group_if_needed(step)
        xml += '<newline/>'
        return xml

    def get_finished_process_xml(self):
        pyson = Bool(Eval('current_state'))
        invisible_def = utils.get_json_from_pyson(pyson)

        xml = '<?xml version="1.0"?>'
        xml += '<form col="4">'
        xml += '<group id="group_tech_complete" '
        xml += 'xfill="1" xexpand="1" yfill="1" yexpand="1" '
        xml += 'states="{'
        xml += "&quot;invisible&quot;: %s" % invisible_def
        xml += '}">'
        xml += '<label id="complete_text" string="%s"/>' % (
            self.raise_user_error('process_completed', raise_exception=False))
        xml += '</group>'
        xml += '</form>'

        return xml

    def get_xml_for_buttons(self, step_relation):
        xml = ''
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

    def build_xml_step_form(self, step):
        xml = '<?xml version="1.0"?>'
        xml += '<form col="4">'
        xml += '<group id="process_content" '
        xml += 'xfill="1" xexpand="1" yfill="1" yexpand="1">'
        xml += self.get_xml_header()
        xml += self.get_xml_for_step(step)
        xml += '<newline/>'
        xml += '</group>'
        if self.step_button_group_position:
            if self.step_button_group_position == 'bottom':
                xml += '<newline/>'
            xml += '<group id="process_buttons" colspan="1" col="1" '
            if self.step_button_group_position == 'right':
                xml += 'xexpand="0" xfill="0" yexpand="1" yfill="1">'
            elif self.step_button_group_position == 'bottom':
                xml += 'xexpand="1" xfill="1" yexpand="0" yfill="0">'
            xml += self.get_xml_for_buttons(step)
            xml += '</group>'
        xml += '<newline/>'
        xml += self.get_xml_footer()
        xml += '</form>'
        # Prettify xml to ease reading
        return lxml.etree.tostring(lxml.etree.fromstring(xml),
            pretty_print=True)

    def get_view(self, relation_step):
        pool = Pool()
        View = pool.get('ir.ui.view')
        current_lang = Transaction().context.get('language')

        view_name = 'process_view_%s_%s' % (str(relation_step.id), current_lang)
        views = View.search([('name', '=', view_name)], limit=1)

        if not views:
            view = View()
            view.model = self.on_model.model
            view.name = view_name
            view.type = 'form'
            view.module = 'process_views'
            view.priority = 100
        else:
            view = views[0]
        view.arch = self.build_xml_step_form(relation_step)
        return view

    def refresh_views(self):
        # A process view is created from the proces configuration for each step
        # and for each language.
        pool = Pool()
        Lang = pool.get('ir.lang')
        View = pool.get('ir.ui.view')
        languages = Lang.search(['OR',
                ('translatable', '=', True),
                ('code', '=', 'en'),
                ])

        views = []
        for lang in languages:
            with Transaction().set_context(language=lang.code):
                for relation_step in self.all_steps:
                    views.append(self.get_view(relation_step))
            view_name = 'process_view_%s_terminated_%s' % (
                self.on_model.model, lang.code)
            terminated_views = View.search([('name', '=', view_name)], limit=1)
            if not terminated_views:
                terminated_view = View()
                terminated_view.name = view_name
                terminated_view.model = self.on_model.model
                terminated_view.type = 'form'
                terminated_view.module = 'process_views'
                terminated_view.priority = 100
            else:
                terminated_view = terminated_views[0]
            terminated_view.arch = self.get_finished_process_xml()
            views.append(terminated_view)

        View.save(views)

    def get_step_relation(self, step):
        for elem in self.all_steps:
            if elem.step.id == step.id:
                return elem
        return None

    def first_step(self):
        for elem in self.transitions:
            if elem.kind != 'start' or not elem.to_step:
                continue
            return self.get_step_relation(elem.to_step)
        return self.all_steps[0]

    def get_rec_name(self, name):
        return self.fancy_name

    @classmethod
    def create(cls, values):
        processes = super(Process, cls).create(values)
        for process in processes:
            process.refresh_views()
        return processes

    @classmethod
    def write(cls, *args):
        # Each time we write the process, we update the view
        super(Process, cls).write(*args)
        for process in sum(args[0::2], []):
            process.refresh_views()

    @classmethod
    def delete(cls, processes):
        pool = Pool()
        Lang = pool.get('ir.lang')
        View = pool.get('ir.ui.view')
        languages = Lang.search(['OR',
                ('translatable', '=', True),
                ('code', '=', 'en'),
                ])
        views = []
        for lang in languages:
            for process in processes:
                for relation_step in process.all_steps:
                    views.append(
                        'process_view_%s_%s' % (relation_step.id, lang.code))
        if views:
            View.delete(View.search([('name', 'in', views)]))
        super(Process, cls).delete(processes)

    def get_action(self, instance):
        # Create a temporary act_window action and insert the process views
        View = Pool().get('ir.ui.view')
        lang = Transaction().context.get('language') or Transaction().language
        act_window = {}
        act_window['id'] = None
        act_window['res_model'] = instance.__name__
        act_window['context'] = json.dumps(self.get_action_context())
        act_window['domain'] = '[["current_state", "in", (%s)]]' % (
            ','.join(map(lambda x: str(x.id), self.all_steps)))
        act_window['context_module'] = None
        act_window['type'] = 'ir.action.act_window'
        act_window['pyson_order'] = 'null'
        act_window['pyson_search_value'] = '[]'
        act_window['domains'] = []
        act_window['context_model'] = None
        act_window['name'] = self.fancy_name

        view_names = ['process_view_%s_%s' % (s.id, lang)
            for s in self.all_steps]

        views = View.search([('name', 'in', view_names)])
        act_window['views'] = []
        for index, view in enumerate(views):
            if (hasattr(instance, 'current_state') and
                    int(view.name.split('_')[2]) == instance.current_state.id):
                act_window['views'].insert(0, (view.id, view.type))
            else:
                act_window['views'].append((view.id, view.type))
        return act_window

    @fields.depends('fancy_name', 'technical_name')
    def on_change_with_technical_name(self):
        if self.technical_name:
            return self.technical_name
        return coog_string.slugify(self.fancy_name)

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
                method(target, *parameters)
            else:
                method(target)

        if self.content != 'method':
            raise NotImplementedError
        if not target.__name__ == self.on_model.model:
            raise Exception('Bad models ! Expected %s got %s' % (
                    self.on_model.model, target.__name__))
        # Test if classmethod or not
        method = getattr(target.__class__, self.method_name)
        if model.is_class_or_dual_method(method):
            target = [target]
        call_method(method, target, self.parameters)

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
        except Exception:
            return self.raise_user_error('source_code_unavailable',
                raise_exception=False)

    def get_on_model(self, name):
        if self.parent_step and self.parent_step.main_model:
            # TODO : to change from process module to coog_process
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
        ondelete='CASCADE', states={
            'required': Eval('kind') != 'start',
            'invisible': Eval('kind') == 'start'},
        depends=['kind'])
    to_step = fields.Many2One('process.step', 'To Step', ondelete='CASCADE',
        domain=[('id', '!=', Eval('from_step'))],
        states={'invisible': Eval('kind') == 'complete',
            'required': Eval('kind') == 'start'},
        depends=['from_step', 'kind'])
    kind = fields.Selection([
            ('start', 'Start Process'),
            ('standard', 'Standard Transition'),
            ('complete', 'Complete Process')],
        'Transition Kind', required=True)
    name = fields.Char('Name', states={
            'required': Eval('kind') == 'complete',
            'invisible': Eval('kind') != 'complete',
            }, depends=['kind'], translate=True)
    # Could be useful if we need to find the dependencies of the pyson expr :
    #  re.compile('Eval\(\'([a-zA-Z0-9._]*)\'', re.I|re.U) + finditer
    pyson = fields.Char('Pyson Constraint', states={
            'invisible': Eval('kind') == 'draft'}, depends=['kind'])
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
        cls._order = [('priority', 'ASC')]
        cls._error_messages.update({
                'complete_button_label': 'Complete',
                })

    @classmethod
    def __register__(cls, module):
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().connection.cursor()
        transition_h = TableHandler(cls, module)
        to_migrate = not transition_h.column_exist('name')
        super(ProcessTransition, cls).__register__(module)

        # Migrate from 1.10 : Allow to customize complete transition name
        to_update = cls.__table__()
        if to_migrate:
            cursor.execute(*to_update.update(
                    columns=[to_update.name],
                    values=[Literal('Complete')],
                    where=to_update.kind == 'complete',
                    ))

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
            xml = '<button string="%s" ' % self.name
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
            Process(process).refresh_views()

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
                auths.append(In(elem.id, Get(
                            Eval('context', {}), 'groups', [])))
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
            return coog_string.slugify(self.fancy_name)

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

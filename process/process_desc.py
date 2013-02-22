import pydot

from trytond.model import fields
from trytond.model import ModelView, ModelSQL
from trytond.wizard import Wizard, StateAction
from trytond.report import Report
from trytond.transaction import Transaction
from trytond.pyson import Eval
from trytond.pool import Pool

from trytond.modules.coop_utils import coop_string

__all__ = [
    'Status',
    'ProcessStepRelation',
    'ProcessDesc',
    'TransitionAuthorization',
    'StepTransition',
    'StepDesc',
    'StepDescAuthorization',
    'GenerateGraph',
    'GenerateGraphWizard',
]


class Status(ModelSQL, ModelView):
    'Process Status'

    __name__ = 'process.status'

    name = fields.Char('Name', required=True, translate=True)
    code = fields.Char('Code', required=True)
    relations = fields.One2Many(
        'process.process_step_relation', 'status', 'Relations',
        states={'readonly': True})


class ProcessStepRelation(ModelSQL, ModelView):
    'Process to Step relation'

    __name__ = 'process.process_step_relation'

    process = fields.Many2One(
        'process.process_desc',
        'Process',
        ondelete='CASCADE',
    )

    step = fields.Many2One(
        'process.step_desc',
        'Step',
        ondelete='RESTRICT',
    )

    status = fields.Many2One(
        'process.status',
        'Status',
        ondelete='RESTRICT',
    )

    order = fields.Integer(
        'Order',
    )

    def get_rec_name(self, name):
        return self.process.get_rec_name(name) + ' - ' + \
            self.status.get_rec_name(name)


class ProcessDesc(ModelSQL, ModelView):
    'Process Descriptor'

    __name__ = 'process.process_desc'

    # This name must be unique in the database, in order to avoid mismatching
    # as it is the key which will be passed in the context
    technical_name = fields.Char(
        'Technical Name',
    )

    # We also need a name which we can display to the final user
    fancy_name = fields.Char(
        'Name', translate=True
    )

    # A given process can only be used on a given model
    on_model = fields.Many2One(
        'ir.model',
        'On Model',
        # This model must be workflow compatible
        domain=[
            ('is_workflow', '=', True),
            ('model', '!=', 'process.process_framework')
        ],
    )

    # We also need all the steps that will be used in the process
    all_steps = fields.One2Many(
        'process.process_step_relation',
        'process',
        'All Steps',
        order=[('order', 'ASC')],
    )

    transitions = fields.One2Many(
        'process.step_transition',
        'on_process',
        'Transitions',
    )

    # We might want to cusomize our process screen
    xml_header = fields.Text(
        'Header XML',
    )

    xml_footer = fields.Text(
        'Footer XML',
    )

    # We also need a way to present the processes in tree views
    xml_tree = fields.Text(
        'Tree View XML',
    )

    step_button_group_position = fields.Selection(
        [('', 'None'), ('right', 'Right'), ('bottom', 'Bottom')],
        'Process Overview Positioning',
    )

    # We need to be able to specify where the entry point to launch the process
    # will be displayed.
    menu_top = fields.Many2One(
        'ir.ui.menu',
        'Top Menu',
    )

    menu_item = fields.Many2One(
        'ir.ui.menu',
        'Menu Element',
    )

    menu_icon = fields.Selection(
        'list_icons',
        'Menu Icon',
    )

    menu_name = fields.Char(
        'Menu name',
        on_change_with=['fancy_name', 'menu_name'],
    )

    @classmethod
    def __setup__(cls):
        super(ProcessDesc, cls).__setup__()
        cls._buttons.update({
            'update_view': {
                'invisible': ~Eval('id')}})
        cls._sql_constraints += [(
            'unique_tech_name', 'UNIQUE(technical_name)',
            'The technical name must be unique')]

    @classmethod
    def default_step_button_group_position(cls):
        return 'bottom'

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
                good_menu = process.create_update_menu_entry()
                if good_menu:
                    process.menu_item = good_menu
                    process.save()

    def get_all_steps(self):
        # We need a way to get all the steps.
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
            if trans.from_step == step_relation.step and \
                    trans.kind == 'complete':
                result['complete'] = trans
                break

        return result

    def create_or_update_menu(self, good_action):
        MenuItem = Pool().get('ir.ui.menu')
        good_menu = self.menu_item
        if not good_menu:
            good_menu = MenuItem()

        good_menu.parent = self.menu_top
        good_menu.name = self.menu_name
        good_menu.sequence = 10
        good_menu.action = good_action
        good_menu.icon = self.menu_icon

        good_menu.save()

        return good_menu

    def create_or_update_action(self):
        ActWin = Pool().get('ir.action.act_window')

        if ((hasattr(self, 'menu_item') and self.menu_item) and
                hasattr(self.menu_item, 'action') and self.menu_item.action):
            good_action = self.menu_item.action
        else:
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
            xml += '<label id="noauth_text" string="The current record is\
in a state (%s) that you are not allowed to view."/>' % step.fancy_name
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
                xml += '<button string="%s" name="_button_current_%s"/>' % (
                    the_step.fancy_name, self.id)
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
        xml += '<label id="complete_text" string="The current record \
completed the current process, please go ahead"/>'
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
            act_views = ActView.search([
                ('act_window', '=', for_action),
            ])
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

        good_action = self.create_or_update_action()
        good_menu = self.create_or_update_menu(good_action)
        self.create_or_update_view(good_action, 'tree')
        self.create_or_update_view(good_action, 'form')

        # We return the good_menu so that it can be set in the menu_item field
        return good_menu

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

    @classmethod
    def create(cls, values):
        # When creating the process, we create the associated view
        processes = super(ProcessDesc, cls).create(values)

        for process in processes:
            menu = process.create_update_menu_entry()

            # Then save the menu in the menu_item field
            if not process.menu_item:
                cls.write([process], {'menu_item': menu})

        return processes

    @classmethod
    def write(cls, instances, values):
        # Each time we write the process, we update the view
        super(ProcessDesc, cls).write(instances, values)

        if 'menu_item' in values:
            return

        for process in instances:
            menu = process.create_update_menu_entry()

            if not process.menu_item:
                cls.write([process], {'menu_item': menu})

    @classmethod
    def delete(cls, processes):
        MenuItem = Pool().get('ir.ui.menu')
        ActWin = Pool().get('ir.action.act_window')
        View = Pool().get('ir.ui.view')

        menus = []
        act_wins = []
        views = []

        for process in processes:
            if process.menu_item:
                menus.append(process.menu_item)
                act_wins.append(process.menu_item.action)
                for view in process.menu_item.action.act_window_views:
                    views.append(view.view)

        MenuItem.delete(menus)
        ActWin.delete(act_wins)
        View.delete(views)

        super(ProcessDesc, cls).delete(processes)


class TransitionAuthorization(ModelSQL):
    'Transition Authorization'

    __name__ = 'process.transition_authorization'

    transition = fields.Many2One(
        'process.step_transition',
        'Transition',
        ondelete='CASCADE',
    )

    group = fields.Many2One(
        'res.group',
        'Group',
        ondelete='CASCADE',
    )


class StepTransition(ModelSQL, ModelView):
    'Step Transition'

    __name__ = 'process.step_transition'

    on_process = fields.Many2One(
        'process.process_desc',
        'On Process',
        required=True,
        ondelete='CASCADE',
    )

    # Transitions go FROM one step...
    from_step = fields.Many2One(
        'process.step_desc',
        'From Step',
        ondelete='CASCADE',
        required=True,
    )

    # TO another
    to_step = fields.Many2One(
        'process.step_desc',
        'To Step',
        ondelete='CASCADE',
        # (they cannot be the same)
        domain=[('id', '!=', Eval('from_step'))],
        depends=['from_step'],
        states={
            'invisible': Eval('kind') != 'standard',
        },
    )

    # Theoratically, there might be a difference between going from B to A
    # depending on whether we alredy went through A or not
    kind = fields.Selection(
        [
            ('standard', 'Standard Transition'),
            ('complete', 'Complete Process'),
        ],
        'Transition Kind',
        required=True,
    )

    # We might want to have a little more control on whether we display a
    # transition or not.
    # Could be useful if we need to find the dependencies of the pyson expr :
    #  re.compile('Eval\(\'([a-zA-Z0-9._]*)\'', re.I|re.U) + finditer
    pyson = fields.Char(
        'Pyson Constraint',
    )

    # The purpose of a transition is to execute some code, let's do this !
    methods = fields.Text(
        'Methods',
        states={
            'invisible': Eval('kind') != 'standard',
        },
    )

    method_kind = fields.Selection(
        [
            ('replace', 'Replace Step Methods'),
            ('add', 'Executed between steps')],
        'Method Behaviour',
        states={
            'invisible': Eval('kind') != 'standard',
        },
    )

    # And authorizations are needed to filter users
    authorizations = fields.Many2Many(
        'process.transition_authorization',
        'transition',
        'group',
        'Authorizations',
    )

    # We need to be able to order the transitions
    priority = fields.Integer(
        'Priority',
    )

    def execute(self, target):
        if (self.kind == 'standard' and self.is_forward() or
                self.kind == 'complete') and self.method_kind == 'add':
            self.from_step.execute_after(target)
        # Executing a transition is easy : just apply all methods
        if self.methods:
            for method in self.methods.split('\n'):
                if not method:
                    continue
                try:
                    # All methods should return a result, and errors
                    result = getattr(target, method.strip())()
                except:
                    print 'Error for method ', method
                    raise

                if not isinstance(result, (list, tuple)) and result is True:
                    continue

                # In case of errors, display them !
                res, errs = result
                if not res or errs:
                    target.raise_user_error(errs)

        if self.kind == 'standard' and self.is_forward and \
                self.method_kind == 'add':
            self.to_step.execute_before(target)

        # Everything went right, update the state of the instance
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
                self.to_step.fancy_name,
                self.on_process.id,
                self.id)
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
        if not self.pyson:
            pyson = None
        else:
            pyson = self.pyson

        return pyson


class StepDescAuthorization(ModelSQL):
    'Step Desc Authorization'

    __name__ = 'process.step_desc_authorization'

    step_desc = fields.Many2One(
        'process.step_desc',
        'Step Desc',
        ondelete='CASCADE',
    )

    group = fields.Many2One(
        'res.group',
        'Group',
        ondelete='CASCADE',
    )


class StepDesc(ModelSQL, ModelView):
    'Step Descriptor'

    __name__ = 'process.step_desc'
    _rec_name = 'fancy_name'

    # The technical_name is a functional name to identify the step desc in a
    # friendlier way than just the id.
    technical_name = fields.Char(
        'Technical Name', on_change_with=['technical_name', 'fancy_name'])
    # We also need a really fancy way to present the current state
    fancy_name = fields.Char('Name', translate=True)

    # Finally, the xml which will be displayed on the current state.
    step_xml = fields.Text(
        'XML',
    )

    authorizations = fields.Many2Many(
        'process.step_desc_authorization',
        'step_desc',
        'group',
        'Authorizations',
    )

    code_before = fields.Text(
        'Exectuted Before Step',
    )

    code_after = fields.Text(
        'Executed After Step',
    )

    colspan = fields.Integer(
        'View columns',
        required=True,
    )

    @classmethod
    def __setup__(cls):
        super(StepDesc, cls).__setup__()
        cls._sql_constraints += [(
            'unique_tech_name', 'UNIQUE(technical_name)',
            'The technical name must be unique')]

    @classmethod
    def write(cls, steps, values):
        super(StepDesc, cls).write(steps, values)

        # If we write a step that's being used in the definition of a process
        ProcessStepRelation = Pool().get('process.process_step_relation')
        processes = set()

        for step in steps:
            used_in = ProcessStepRelation.search([
                ('step', '=', step)])
            processes |= set(map(lambda x: x.process.id, used_in))

        if not processes:
            return

        Process = Pool().get('process.process_desc')
        # We need to update each of those processes view.
        for process in processes:
            Process(process).create_update_menu_entry()

    def execute_code(self, target, code):
        for method in code.split('\n'):
            if not method:
                continue
            try:
                # All methods should return a result, and errors
                result = getattr(target, method.strip())()
            except:
                print 'Error for method ', method
                raise

            if not isinstance(result, (list, tuple)) and result is True:
                continue

            # In case of errors, display them !
            res, errs = result
            if not res or errs:
                target.raise_user_error(errs)

    def execute_before(self, target):
        if not self.code_before:
            return

        self.execute_code(target, self.code_before)

    def execute_after(self, target):
        if not self.code_after:
            return

        self.execute_code(target, self.code_after)

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
    __name__ = 'process.graph_generation'

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
        nodes[step.id] = pydot.Node(
            step.fancy_name,
            style='filled',
            shape='rect',
            fontname='Century Gothic',
        )

        # if not step.to_steps:
            # nodes[step.id].set('style', 'filled')
            # nodes[step.id].set('shape', 'circle')
            # nodes[step.id].set('fillcolor', '#a2daf4')

    @classmethod
    def build_transition(cls, process, step, transition, graph, nodes, edges):
        good_edge = pydot.Edge(
            nodes[transition.from_step.id],
            nodes[transition.to_step.id],
            fontname='Century Gothic',
        )
        good_edge.set('len', '1.0')
        good_edge.set('constraint', '1')
        good_edge.set('weight', '1.0')

        edges[(step.id, transition.to_step.id)] = good_edge

    @classmethod
    def build_inverse_transition(
            cls, process, step, transition, graph, nodes, edges):
        tr_fr, tr_to = transition.from_step.id, transition.to_step.id
        if (tr_to, tr_fr) in edges:
            edges[(tr_to, tr_fr)].set('dir', 'both')
        else:
            good_edge = pydot.Edge(
                nodes[transition.from_step.id],
                nodes[transition.to_step.id],
                fontname='Century Gothic',
            )

            good_edge.set('constraint', '0')
            good_edge.set('weight', '0.2')

            edges[(tr_fr, tr_to)] = good_edge

    @classmethod
    def build_complete_transition(
            cls, process, step, transition, graph, nodes, edges):
        nodes['tr%s' % transition.id] = pydot.Node(
            'Complete',
            style='filled',
            shape='circle',
            fontname='Century Gothic',
            fillcolor='#ff0000',
        )

        edges[(transition.from_step.id, 'tr%s' % transition.id)] = pydot.Edge(
            nodes[transition.from_step.id],
            nodes['tr%s' % transition.id],
            fontname='Century Gothic',
            len=1.0,
            constraint=1,
            weight=1.0
        )

    @classmethod
    def execute(cls, ids, data):
        ActionReport = Pool().get('ir.action.report')

        action_report_ids = ActionReport.search([
            ('report_name', '=', cls.__name__)
        ])
        if not action_report_ids:
            raise Exception('Error', 'Report (%s) not find!' % cls.__name__)
        action_report = ActionReport(action_report_ids[0])

        Process = Pool().get('process.process_desc')
        the_process = Process(Transaction().context.get('active_id'))

        graph = cls.build_graph(the_process)

        nodes = {}

        for step in the_process.get_all_steps():
            cls.build_step(the_process, step, graph, nodes)

        edges = {}

        for transition in the_process.transitions:
            if transition.kind == 'standard' and transition.is_forward():
                cls.build_transition(
                    the_process, step, transition, graph, nodes, edges)

        for transition in the_process.transitions:
            if transition.kind == 'standard' and transition.is_forward():
                cls.build_inverse_transition(
                    the_process, step, transition, graph, nodes, edges)

        for transition in the_process.transitions:
            if transition.kind == 'complete':
                cls.build_complete_transition(
                    the_process, step, transition, graph, nodes, edges)

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
    __name__ = 'process.generate_graph_wizard'

    start_state = 'print_'

    print_ = StateAction('process.report_generate_graph')

    def transition_print_(self):
        return 'end'

    def do_print_(self, action):
        return action, {
            'id': Transaction().context.get('active_id'),
        }

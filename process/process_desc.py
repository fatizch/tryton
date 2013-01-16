import pydot

from trytond.model import fields
from trytond.model import ModelView, ModelSQL
from trytond.wizard import Wizard, StateAction
from trytond.report import Report
from trytond.transaction import Transaction
from trytond.pyson import Eval

from trytond.pool import Pool

from trytond.modules.coop_utils import One2ManyDomain


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

    name = fields.Char(
        'Name',
        required=True,
    )

    code = fields.Char(
        'Code',
        required=True,
    )

    relations = fields.One2Many(
        'process.process_step_relation',
        'status',
        'Relations',
        states={
            'readonly': True
        },
    )


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
    )

    status = fields.Many2One(
        'process.status',
        'Status',
        ondelete='RESTRICT',
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
        'Name',
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

    # We need to distinguish the first step from the others. We need to know
    # where to start.
    first_step = fields.Many2One(
        'process.step_desc',
        'First Step',
    )

    # We also need all the steps that will be used in the process
    all_steps = fields.One2Many(
        'process.process_step_relation',
        'process',
        'All Steps',
    )

    # We might want to cusomize our process screen
    xml_header = fields.Text(
        'XML',
    )

    xml_footer = fields.Text(
        'XML',
    )

    # We also need a way to present the processes in tree views
    xml_tree = fields.Text(
        'XML',
    )

    # We need to be able to specify where the entry point to launch the process
    # will be displayed.
    menu_top = fields.Many2One(
        'ir.ui.menu',
        'Top Menu',
        # Only if the menu does not exist yet !
        states={
            'invisible': ~~Eval('menu_item')
        },
    )

    # Once the menu exists, here is how to find it !
    menu_item = fields.Many2One(
        'ir.ui.menu',
        'Menu Element',
        states={
            'invisible': ~Eval('menu_item')
        },
    )

    @classmethod
    def __setup__(cls):
        super(ProcessDesc, cls).__setup__()
        cls._buttons.update({
            'update_view': {
                'invisible': ~Eval('id')}})

    @classmethod
    @ModelView.button
    def update_view(cls, processes):
        # This button is just used to trigger the update process of the view
        # associated to the process
        with Transaction().set_user(0):
            for process in processes:
                if isinstance(process, int):
                    process = cls(process)
                good_menu = process.create_update_view()
                if good_menu:
                    process.menu_item = good_menu
                    process.save()

    def get_all_steps(self):
        # We need a way to get all the steps.
        for elem in self.all_steps:
            yield elem.step

    def build_steps_tree(self):
        steps = dict([(elem.id, {'from': set([]), 'to': set([])}) 
            for elem in self.get_all_steps()])
        for step_rel in self.all_steps:
            step = step_rel.step
            for prev_trans in step.from_steps:
                if prev_trans.to_step in steps.keys():
                    steps[step.id]['from'].add(prev_trans.to_step.id)
                    steps[prev_trans.to_step.id]['to'].add(step.id)
                        
            for next_trans in step.to_steps:
                if next_trans.to_step.id in steps.keys():
                    steps[step.id]['to'].add(next_trans.to_step.id)
                    steps[next_trans.to_step.id]['from'].add(step.id)
        
        res = {}
        for step in self.all_steps:
            used_steps = set([step.id])

            def get_tree(step_id, used, kind, step_first=True):
                used.add(step_id)
                if not steps[step_id][kind] and not step_id in used:
                    return [step_id]
                res = []
                for elem in steps[step_id][kind]:
                    res.extend(get_tree(elem, used, kind, step_first))

                if step_first:
                    return step_id, res
                else:
                    return res, step_id

            # Remove the current step from the lists:
            res[step.id] = {
                    'from': get_tree(step.id, used_steps, 'from', False)[:-1],
                    'to': get_tree(step.id, used_steps, 'to')[1:],
                }

        return res

    def create_update_view(self):
        # Views are calculated depending on the process' steps and a few other
        # things. In order to avoid runtime calculation, we store the views in
        # the database and provide access to them through a dedicated entry
        # point which is calculated, then can be modified / cloned.

        MenuItem = Pool().get('ir.ui.menu')
        ActWin = Pool().get('ir.action.act_window')
        ActView = Pool().get('ir.action.act_window.view')
        View = Pool().get('ir.ui.view')

        good_menu = self.menu_item
        if not good_menu:
            good_menu = MenuItem()

        # If the menu_item already exists, no need to change this
        if not (hasattr(self, 'menu_item') and self.menu_item):
            good_menu.parent = self.menu_top

        # But we need to update its name if the process' changed
        good_menu.name = self.fancy_name

        good_menu.sequence = 10

        # We fetch the action associated to the menu if it exists, or create it
        # if it does not.
        if (hasattr(good_menu, 'action') and good_menu.action):
            good_action = good_menu.action
        else:
            good_action = ActWin()

        good_action.name = self.fancy_name

        # We set the good model (that is, the model on which the process is
        # defined)
        good_action.res_model = self.on_model.model

        # And we set the context in order to know which process is going on
        # here !
        good_action.context = "{'running_process': '%s'}" % (
            self.technical_name)

        # We also have to filter the states:
        good_action.domain = "[('current_state', 'in', [%s])]" % (
            ','.join(map(lambda x: str(x.id), self.all_steps)))

        good_action.sequence = 10

        # Now we can save the action and the menu
        good_action.save()

        good_menu.action = good_action

        good_menu.save()

        # Now we look for the act_form that match our process
        try:
            act_forms = ActView.search([
                    ('act_window', '=', good_action),
                ])
            act_form = None
            for act in act_forms:
                if not act.view.type == 'form':
                    continue
                act_form = act
                break

        except ValueError:
            act_form = None

        if not act_form:
            good_form = View()
            act_form = ActView()
        else:
            good_form = act_form.view

        # It must be set on the right model, and have the proper name / type
        good_form.model = self.on_model.model
        good_form.name = '%s_form' % self.technical_name
        good_form.type = 'form'

        #TODO: Which modules should be used here ?
        good_form.module = 'process'

        good_form.priority = 10

        # Now we can build the xml !
        xml = '<?xml version="1.0"?>'
        xml += '<form string="%s">' % self.fancy_name
        xml += '<group name="process_header">'
        xml += '</group>'
        xml += '<newline/>'

        # We need to have cur_state in the view so our Pyson Eval can work 
        # properly
        xml += '<field name="current_state" invisible="1"/>'
        xml += '<newline/>'
        xml += '<group name="process_content" '
        xml += 'xfill="1" xexpand="1" yfill="1" yexpand="1">'

        # Now we can build the steps' xml
        for step_relation in self.all_steps:
            step = step_relation.step
            step_xml = "(Eval('current_state', 0) == %s)" % (
                step_relation.id)

            if step.authorizations:
                auth_xml = '('
                for elem in step.authorizations:
                    auth_xml += "Eval('groups', []).contains(%s) or " % elem.id

                auth_xml = auth_xml[:-4] + ')'
            else:
                auth_xml = None

            xml += '<newline/>'
            # The xml of each step is contains inside a group that will have
            # a pyson expression calculated in order to display it only when
            # it should be.
            xml += '<group name="group_%s" ' % step.technical_name
            xml += 'xfill="1" xexpand="1" yfill="1" yexpand="1" '
            xml += 'states="{'
            xml += "'invisible': "

            if auth_xml:
                xml += 'Not(And(%s, %s))' % (step_xml, auth_xml)
            else:
                xml += 'Not(%s)' % step_xml

            xml += '}">'

            # Inside the group, we get the xml calculated on the step
            xml += step.calculate_form_view()
            xml += '</group>'

            if auth_xml:
                xml += '<group name="group_%s_noauth" ' % step.technical_name
                xml += 'xfill="1" xexpand="1" yfill="1" yexpand="1" '
                xml += 'states="{'
                xml += "'invisible': Not(And(%s, Not(%s)))" % (
                    step_xml, auth_xml)
                xml += '}">'
                xml += '<label id="noauth_text" string="The current record is\
 in a state (%s) that you are not allowed to view."/>' % step.fancy_name
                xml += '</group>'

        xml += '<newline/>'
        # We need a special form to explain that the current record
        # completed the process
        xml += '<group name="group_tech_complete" '
        xml += 'xfill="1" xexpand="1" yfill="1" yexpand="1" '
        xml += 'states="{'
        xml += "'invisible': ~~Eval('current_state')"
        xml += '}">'

        xml += '<label id="complete_text" string="The current record \
completed the current process, please go ahead"/>'
        xml += '</group>'

        xml += '</group>'

        xml += '<newline/>'
        xml += '<group name="process_footer">'
        xml += '</group>'
        xml += '</form>'
        
        # Our xml is complete, we set it on the good view, then save it.
        good_form.arch = xml
        good_form.save()

        act_form.act_window = good_action

        act_form.sequence = 10

        # We set this view as the target of the act_form, then save it.
        act_form.view = good_form

        act_form.save()

        # Now we look for (or create) the act_tree for our process :
        try:
            act_trees = ActView.search([
                    ('act_window', '=', good_action),
                ])
            act_tree = None
            for act in act_trees:
                if not act.view.type == 'tree':
                    continue
                act_tree = act
                break

        except ValueError:
            act_tree = None

        if not act_tree:
            act_tree = ActView()

        # We look for the good tree view
        try:
            good_tree, = View.search([
                    ('model', '=', self.on_model.model),
                    ('type', '=', 'tree'),
                    ('name', '=', '%s_tree' % self.technical_name),
                ], limit=1)
        except ValueError:
            # or create it if needed.
            good_tree = View()

        # We set the model, name and type of the view
        good_tree.model = self.on_model.model
        good_tree.name = '%s_tree' % self.technical_name
        good_tree.type = 'tree'

        #TODO: Which modules should be used here ?
        good_tree.module = 'process'

        good_tree.priority = 10

        # Add some very basic xml
        xml = '<?xml version="1.0"?>'
        xml += '<tree string="%s">' % self.fancy_name
        xml += self.xml_tree
        xml += '</tree>'

        good_tree.arch = xml

        # save it
        good_tree.save()

        act_tree.act_window = good_action

        act_tree.sequence = 1

        # Completing the act_tree and saving it
        act_tree.view = good_tree
        act_tree.save()

        # We are done (the links between the act_tree/form and the act_window
        # are reversed, nothing to set here.

        # We return the good_menu so that it can be set in the menu_item field
        return good_menu

    def get_step_relation(self, step):
        for elem in self.all_steps:
            if elem.step.id == step.id:
                return elem

        return None
    
    def get_first_state_relation(self):
        return self.get_step_relation(self.first_step)
    
    def get_rec_name(self, name):
        return self.fancy_name

    @classmethod
    def create(cls, values):
        # When creating the process, we create the associated view
        processes = super(ProcessDesc, cls).create(values)

        for process in processes:
            menu = process.create_update_view()

            # Then save the menu in the menu_item field
            if not process.menu_item:
                cls.write([process], {'menu_item': menu})

        return processes

    @classmethod
    def write(cls, instances, values):
        # Each time we write the process, we update the view
        super(ProcessDesc, cls).write(instances, values)

        for process in instances:
            menu = process.create_update_view()

            if not process.menu_item:
                cls.write([process], {'menu_item': menu})


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

    # Transitions go FROM one step...
    from_step = fields.Many2One(
        'process.step_desc',
        'From Step',
        ondelete='CASCADE',
    )

    # TO another
    to_step = fields.Many2One(
        'process.step_desc',
        'To Step',
        ondelete='CASCADE',
        # (they cannot be the same)
        domain=[('id', '!=', Eval('from_step'))],
        depends=['from_step'],
    )

    # Theoratically, there might be a difference between going from B to A
    # depending on whether we alredy went through A or not
    kind = fields.Selection(
        [
            ('previous', 'Previous Transition'),
            ('next', 'Next Transition'),
            # Some special steps need to be distinguished.
            ('other', 'Other Transition'),
        ],
        'kind',
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
    )

    # And authorizations are needed to filter users
    authorizations = fields.Many2Many(
        'process.transition_authorization',
        'transition',
        'group',
        'Authorizations',
    )

    # Sometimes we just want to display a readonly button for aesthetics
    is_readonly = fields.Boolean('Readonly')

    # We need to be able to order the transitions
    priority = fields.Integer(
        'Priority',
    )

    def execute(self, target):
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

                if not isinstance(result, (list, tuple)) and result == True:
                    continue

                # In case of errors, display them !
                res, errs = result
                if not res or errs:
                    target.raise_user_error(errs)

        # Everything went right, update the state of the instance
        target.set_state(self.to_step)

    def build_button(self):
        # Here we build the xml for the button associated to the transition.
        # What must be build is the button name, in which we encode the ids
        # of the from and to steps.
        xml = '<button string="%s" name="_button_%s"/>' % (
            self.to_step.fancy_name,
            self.id)

        return xml

    def get_rec_name(self, name):
        return self.to_step.get_rec_name(name)

    @classmethod
    def default_methods(cls):
        return ''


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
        'Technical Name',
    )

    # We also need a really fancy way to present the current state
    fancy_name = fields.Char(
        'Name',
    )

    # We need the list of transitions which will be end on this step
    from_steps = One2ManyDomain(
        'process.step_transition',
        'from_step',
        'From Steps',
        domain=[
            ('kind', '=', 'previous')],
        order=[('priority', 'ASC')],
    )

    # As well as those which will start from this step
    to_steps = One2ManyDomain(
        'process.step_transition',
        'from_step',
        'To Steps',
        domain=[('kind', '=', 'next')],
        order=[('priority', 'ASC')],
    )

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
            Process(process).create_update_view()

    def calculate_form_view(self):
        # Here is the xml definition for this step.
        # First there is the db defined xml :
        xml = '<group name="%s_form" xfill="1" ' % self.technical_name
        xml += 'xexpand="1" yfill="1" yexpand="1">'
        xml += ''.join(self.step_xml.split('\n'))
        xml += '</group>'
        xml += '<newline/>'

        # We need to know how many buttons there will be
        nb_buttons = len(self.from_steps) + len(self.to_steps) + 1

        # Then we add all the buttons for this step
        xml += '<group name="%s_buttons" col="%s">' % (
            self.technical_name, nb_buttons)

        # The "previous" buttons
        for trans in self.from_steps:
            xml += trans.build_button()

        if self.to_steps:
            # The "current state" button
            xml += '<button string="%s" name="_button_%s_%s"/>' % (
                self.fancy_name, self.id, self.id)

            # And the "next buttons"
            for trans in self.to_steps:
                xml += trans.build_button()
        else:
            # If there are no "next" buttons, we need an exit point.
            xml += '<button string="%s" name="_button_%s_complete"/>' % (
                'Complete Process', self.id)

        xml += '</group>'

        return xml


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

        if not step.to_steps:
            nodes[step.id].set('style', 'filled')
            nodes[step.id].set('shape', 'circle')
            nodes[step.id].set('fillcolor', '#a2daf4')

    @classmethod
    def build_transition(cls, process, step, transition, graph, nodes, edges):
        if transition.is_readonly:
            return
        
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
        if transition.is_readonly:
            return

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
        for step in the_process.get_all_steps():
            for transition in step.to_steps:
                cls.build_transition(
                    the_process, step, transition, graph, nodes, edges)


        for step in the_process.get_all_steps():
            for transition in step.from_steps:
                cls.build_inverse_transition(
                    the_process, step, transition, graph, nodes, edges)

        nodes[the_process.first_step.id].set('style', 'filled')
        nodes[the_process.first_step.id].set('shape', 'octagon')
        nodes[the_process.first_step.id].set('fillcolor', '#0094d2')

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



from trytond.model import fields
from trytond.model import ModelView, ModelSQL
from trytond.pyson import Eval

from trytond.pool import Pool

from trytond.modules.coop_utils import One2ManyDomain


__all__ = [
    'ProcessStepRelation',
    'ProcessDesc',
    'TransitionAuthorization',
    'StepTransition',
    'StepDesc',
]


class ProcessStepRelation(ModelSQL):
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
    all_steps = fields.Many2Many(
        'process.process_step_relation',
        'process',
        'step',
        'All Steps',
    )

    # We might want to cusomize our process screen
    xml_header = fields.Text(
        'XML',
    )

    xml_footer = fields.Text(
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
        for process in processes:
            if isinstance(process, int):
                process = cls(process)
            process.create_update_view()

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
        # We need to have cur_state in the view so our Pyson Eval can work 
        # properly
        xml += '<field name="cur_state"/>'
        xml += '</group>'
        xml += '<newline/>'
        xml += '<group name="process_content" '
        xml += 'xfill="1" xexpand="1" yfill="1" yexpand="1">'

        # Now we can build the steps' xml
        for step in self.all_steps:
            xml += '<newline/>'
            # The xml of each step is contains inside a group that will have
            # a pyson expression calculated in order to display it only when
            # it should be.
            xml += '<group name="group_%s" ' % step.technical_name
            xml += 'xfill="1" xexpand="1" yfill="1" yexpand="1" '
            xml += 'states="{'
            xml += "'invisible': Eval('cur_state') != '%s'" % (
                step.technical_name)
            xml += '}">'

            # Inside the group, we get the xml calculated on the step
            xml += step.calculate_form_view()
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

        # For the tree view, we use the model's default tree view :
        try:
            good_tree, = View.search([
                    ('model', '=', self.on_model.model),
                    ('type', '=', 'tree'),
                    ('name', '!=', '%s_tree' % self.technical_name),
                ], limit=1)
        except ValueError:
            # If it does not exist, we look for a generic one
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
            xml += '<field name="rec_name"/>'
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

    @classmethod
    def create(cls, values):
        # When creating the process, we create the associated view
        process = super(ProcessDesc, cls).create(values)

        menu = process.create_update_view()

        # Then save the menu in the menu_item field
        if not process.menu_item:
            cls.write([process], {'menu_item': menu})

        return process

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
        required=True,
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

    def execute(self, target):
        # Executing a transition is easy : just apply all methods
        for method in self.methods.split('\n'):
            if not method:
                continue
            try:
                # All methods should return a result, and errors
                res, errs = getattr(target, method)()
            except:
                raise

            # In case of errors, display them !
            if not res or errs:
                target.raise_user_error(errs)

        # Everything went right, update the state of the instance
        target.set_state(self.to_step.technical_name)

    def build_button(self):
        # Here we build the xml for the button associated to the transition.
        # What must be build is the button name, in which we encode the ids
        # of the from and to steps.
        xml = '<button string="%s" name="_button_%s_%s"/>' % (
            self.to_step.fancy_name,
            self.from_step.id,
            self.to_step.id)

        return xml


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
    )

    # As well as those which will start from this step
    to_steps = One2ManyDomain(
        'process.step_transition',
        'from_step',
        'To Steps',
        domain=[('kind', '=', 'next')],
    )

    # Finally, the xml which will be displayed on the current state.
    step_xml = fields.Text(
        'XML',
    )

    @classmethod
    def write(cls, steps, values):
        super(StepDesc, cls).write(steps, values)

        # If we write a step that's being used in the definition of a process
        Process = Pool().get('process.process_desc')
        processes = set()
        for step in steps:
            used_in = Process.search([
                ('all_steps', '=', 'step')])
            processes |= set(map(lambda x:x.id, used_in))

        # We need to update each of those processes view.
        for process in processes:
            process.create_update_view()

    def calculate_form_view(self):
        # Here is the xml definition for this step.
        # First there is the db defined xml :
        xml = '<group name="%s_form" xfill="1" ' % self.technical_name
        xml += 'xexpand="1" yfill="1" yexpand="1">'
        xml += ''.join(self.step_xml.split('\n'))
        xml += '</group>'
        xml += '<newline/>'

        # Then we add all the buttons for this step
        xml += '<group name="%s_buttons">' % self.technical_name
        
        # The "previous" buttons
        for trans in self.from_steps:
            xml += trans.build_button()

        # The "current state" button
        xml += '<button string="%s" name="_button_%s_%s"/>' % (
            self.fancy_name, self.id, self.id)

        # And the "next buttons"
        for trans in self.to_steps:
            xml += trans.build_button()

        xml += '</group>'

        return xml

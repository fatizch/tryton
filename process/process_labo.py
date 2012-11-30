# -*- coding: utf-8 -*-

# Needed for displaying and storing objects
from trytond.model import fields

from trytond.modules.coop_utils import model

# Needed for easy access to models
from trytond.pool import Pool

# Needed to access transactionnal context
from trytond.transaction import Transaction

# Needed for Eval
from trytond.pyson import Eval

# Needed for RPC calls
from trytond.rpc import RPC

try:
    import simplejson as json
except ImportError:
    import json

# For now, just step_over and checks are customizable
METHOD_TYPES = [
    ('0_step_over', 'Must Step Over'),
    # ('1_before_step', 'Before Step Execution'),
    ('2_check_step', 'Step Validation'),
    # ('3_post_step', 'Step Completion')
]

BUTTONS = [
    ('button_next', "'Next' Button"),
    ('button_previous', "'Previous' Button"),
    ('button_check', "'Check' Button"),
    ('button_complete', "'Complete' Button"),
    ('button_cancel', "'Cancel' Button"),
    ('button_suspend', "'Suspend' Button"),
]

__all__ = [
    'MenuBuilder',
    'StepDescRelation',
    'StepDesc',
    'StepMethodDesc',
]


class NonExistingState(Exception):
    pass


class MenuBuilder(model.CoopView, model.CoopSQL):
    'Menu Builder'

    __name__ = 'process.menu_builder'

    parent_menu = fields.Many2One(
        'ir.ui.menu',
        'Parent',
        required=True
    )

    name = fields.Char(
        'Name',
        required=True
    )

    order = fields.Integer(
        'Order',
        required=True
    )

    step_desc = fields.Many2One(
        'process.step_desc',
        'Step Desc',
        states={
            'invisible': True
        },
        ondelete='CASCADE',
    )


class StepDescRelation(model.CoopSQL):
    'Step Desc Relation'
    __name__ = 'process.step_desc_relation'

    from_step = fields.Many2One(
        'process.step_desc',
        'From Step',
    )

    to_step = fields.Many2One(
        'process.step_desc',
        'To Step',
        ondelete='CASCADE',
    )


class StepDesc(model.CoopSQL, model.CoopView):
    'Step Descriptor'
    __name__ = 'process.step_desc'
    _rec_name = 'step_name'

    # Virtual_step makes the step 'virtual', that is without any form. It is
    # just a way to add user-defined methods between steps
    virtual_step = fields.Boolean('Virtual Step')

    # A given step desc is associated to a model.
    main_model = fields.Many2One(
        'ir.model',
        'Main Model',
    )

    # The model will be selected through the use of a selection field which
    # will use the get_process_name fonction to check that the process inherits
    # from the RichWorkflow class :
    #main_model_selection = fields.Function(
        #fields.Selection(
            #'get_process_models',
            #'Model Selection',
        #),
        #'get_process_model',
        #'set_process_model',
    #)

    # Next possible states. It is a liste of states which will be used to
    # select the next step from
    next_steps = fields.Many2Many(
        'process.step_desc_relation',
        'from_step',
        'to_step',
        'Next Steps',
        # We do not want to cycle on one step (for now)
        domain=[
            ('id', '!=', Eval('id', None)),
            ('main_model', '=', Eval('main_model', None))],
        depends=['id', 'main_model'],
    )

    # A user frinedy name that will be used when displaying the step
    step_name = fields.Char(
        'Step Name',
        required=True,
    )

    # We define the step's technical name, which must be unique among the
    # process defined on one given model
    step_technical_name = fields.Char(
        'Technical Name',
        required=True,
    )

    # We need to specify which field will be used to store the current state
    process_field = fields.Many2One(
        'ir.model.field',
        'Process Field',
        states={
            'readonly': ~Eval('main_model')
        },
        domain=[
            ('model', '=', Eval('main_model')),
            ('name', 'like', 'workflow_%'),
        ],
        depends=['main_model'],
    )

    # We use this selection field to provide the good filters and cleaner
    # inerface to select the field.
    #process_field_selection = fields.Function(
        #fields.Selection(
            #'get_process_fields',
            #'Process Field',
            #context={
                #'process_model': Eval('main_model_selection'),
            #},
            #states={
                #'readonly': ~Eval('main_model_selection')
            #},
        #),
        #'get_process_field',
        #'set_process_field',
    #)

    # We declare a field which will be used to calculate the display field :
    step_xml = fields.Text(
        'Screen Definition',
    )

    # We create a way to build menu items
    menu_elem = fields.Many2One(
        'ir.ui.menu',
        'Menu',
        states={
            'invisible': ~Eval('menu_elem')
        },
    )

    menu_desc = fields.One2Many(
        'process.menu_builder',
        'step_desc',
        'Menu Builder',
        states={
            'invisible': ~~Eval('menu_elem')
        },)

    # Now we need to have a list for each kind of method that will be defined
    # on the step :
    step_over_meths = model.One2ManyDomain(
        'process.step_method_desc',
        'step',
        'Step Over Methods',
        domain=[
            ('rule_kind', '=', 'step_over'),
        ],
        context={
            'main_model': Eval('main_model'),
        },
    )

    before_meths = model.One2ManyDomain(
        'process.step_method_desc',
        'step',
        'Before Methods',
        domain=[
            ('rule_kind', '=', 'before'),
        ],
        context={
            'main_model': Eval('main_model'),
        },
    )

    check_meths = model.One2ManyDomain(
        'process.step_method_desc',
        'step',
        'Check Methods',
        domain=[
            ('rule_kind', '=', 'check'),
        ],
        context={
            'main_model': Eval('main_model'),
        },
    )

    update_meths = model.One2ManyDomain(
        'process.step_method_desc',
        'step',
        'Update Methods',
        domain=[
            ('rule_kind', '=', 'update'),
        ],
        context={
            'main_model': Eval('main_model'),
        },
    )

    validate_meths = model.One2ManyDomain(
        'process.step_method_desc',
        'step',
        'Validate Methods',
        domain=[
            ('rule_kind', '=', 'validate'),
        ],
        context={
            'main_model': Eval('main_model'),
        },
    )

    after_meths = model.One2ManyDomain(
        'process.step_method_desc',
        'step',
        'After Methods',
        domain=[
            ('rule_kind', '=', 'after'),
        ],
        context={
            'main_model': Eval('main_model'),
        },
    )

    button_next = fields.Function(
        fields.Boolean("'Next' button"),
        'get_button',
        setter='set_button')
    button_previous = fields.Function(
        fields.Boolean("'Previous' button"),
        'get_button',
        setter='set_button')
    button_check = fields.Function(
        fields.Boolean("'Check' button"),
        'get_button',
        setter='set_button')
    button_complete = fields.Function(
        fields.Boolean("'Complete' button"),
        'get_button',
        setter='set_button')
    button_cancel = fields.Function(
        fields.Boolean("'Cancel' button"),
        'get_button',
        setter='set_button')
    button_suspend = fields.Function(
        fields.Boolean("'Suspend' button"),
        'get_button',
        setter='set_button')

    button_default = fields.Function(
        fields.Selection(
            BUTTONS,
            'Default Button'),
        'get_button',
        setter='set_button')

    buttons_storage = fields.Char(
        'Buttons',
        states={'invisible': True})

    @classmethod
    def __setup__(cls):
        super(StepDesc, cls).__setup__()
        cls.__rpc__['get_process_models'] = RPC()
        cls.__rpc__['get_process_fields'] = RPC()
        cls._buttons.update({
            'build_ir_elems': {
                'invisible': ~~Eval('menu_elem')}})

    def get_rec_name(self, name):
        return '%s - %s' % (self.step_name, self.main_model.get_rec_name(name))

    @classmethod
    def get_process_models(cls):
        res = []
        for model_name, model in Pool().iterobject():
            if not hasattr(model, 'get_process_name'):
                continue
            good_name = model.get_process_name()
            if good_name:
                res.append((model.__name__, good_name))
        return res
    
    def get_process_model(self, name):
        if hasattr(self, 'main_model') and self.main_model:
            return self.main_model.__name__

    @classmethod
    def set_process_model(cls, steps, name, value):
        # The field main_model_selection uses the model's id as a string, so we
        # just need to convert it back to an int for the storage.
        Model = Pool().get('ir.model')
        StepDesc.write(
            steps,
            {
                'main_model': Model.search([('model', '=', value)])[0]
            }
        )
    
    @classmethod
    def get_process_fields(cls):
        process_name = Transaction().context.get('process_model', None)
        if not process_name:
            return []
        Field = Pool().get('ir.model.field')
        Model = Pool().get('ir.model')
        good_model, = Model.search([
            ('model', '=', process_name)], limit=1)
        good_fields = Field.search([
            ('model', '=', good_model),
            ('name', 'like', 'workflow_%'),
            ('ttype', '=', 'char')])
        return [(field.id, field.field_description) for field in good_fields]

    def get_process_field(self, name):
        if hasattr(self, 'process_field') and self.process_field:
            return self.process_field.id

    @classmethod
    def set_process_field(cls, steps, name, value):
        StepDesc.write(
            steps,
            {
                'process_field': int(value)
            }
        )
    
    # Buttons are all stored in a single field in order to avoid having x
    # columns in the database.
    def get_button(self, name):
        buttons_str = self.buttons_storage
        idx = -1
        for button, _ in BUTTONS:
            idx += 1
            if not button in name:
                continue
            return bool(int(buttons_str[idx]))
        if 'button_default' in name:
            return BUTTONS[int(buttons_str[-1]) - 1][0]

    # We store the buttons associated with the default button name in a single
    # field.
    #
    # Each button is mapped to 0 or 1 depending on whether it is active
    # or not.
    # Then all these values are concatenated in a single char field, with
    # the last value being the index of the default button
    @classmethod
    def set_button(cls, steps, name, value):
        buttons_names = [elem for elem, _ in BUTTONS]
        for step in steps:
            buttons = step.buttons_storage
            buttons_list = list(buttons)
            if name == 'button_default':
                if value in buttons_names:
                    res = str(buttons_names.index(value) + 1)
                else:
                    res = 0
                buttons_list[-1] = str(res)
            else:
                if value:
                    res = '1'
                else:
                    res = '0'
                buttons_list[buttons_names.index(name)] = res
            buttons = ''.join(buttons_list)
            StepDesc.write(
                [step],
                {
                    'buttons_storage': buttons,
                })

    @staticmethod
    def default_buttons_storage():
        return '0000000'

    def calculate_transitions(self, values={}):
        # TODO : Filter by user habilitation
        key = self.step_technical_name
        if not key in values:
            values[key] = set()
        to_call = {} 
        for elem in self.next_steps:
            values[key] |= set((key, elem.step_technical_name))
            if not elem.step_technical_name in values:
                to_call.update({elem.step_technical_name: elem})

        RelationModel = Pool().get('process.step_desc_relation')
        to_call.update(dict(
            map(
                lambda x: (x.from_step.step_technical_name, x.from_step),
                RelationModel.search([('to_step', '=', self)]))))

        for elem in to_call.values():
            if elem.step_technical_name in values:
                continue
            elem.calculate_transitions(values)           

    def manage_this_object(self):
        # TODO : handle authorizations
        return True

    def apply_these_methods(self, meth_type, target):
        for elem in getattr(self, '%s_meths' % meth_type):
            elem.apply_meth(target)

    def next_step(self, target):
        return self.next_steps[0]

    @classmethod
    @model.CoopView.button
    def build_ir_elems(cls, steps):
        for step in steps:
            if not (hasattr(step, 'menu_desc') and step.menu_desc):
                return

            MenuItem = Pool().get('ir.ui.menu')
            ActWin = Pool().get('ir.action.act_window')
            ActView = Pool().get('ir.action.act_window.view')
            View = Pool().get('ir.ui.view')

            act_win = ActWin()
            act_win.name = step.menu_desc[0].name
            act_win.res_model = step.main_model.model
            act_win.context = "{'workflow_field': '%s', " % (
                step.process_field.name)
            act_win.context += "'workflow_value': '%s'}" % (
                step.step_technical_name)
            act_win.sequence = step.menu_desc[0].order
            act_win.domain = "[('%s', '=', '%s')]" % (
                step.process_field.name, step.step_technical_name)
            act_win.save()

            menu = MenuItem()
            menu.parent = step.menu_desc[0].parent_menu
            menu.action = act_win
            menu.sequence = act_win.sequence
            menu.name = act_win.name
            menu.save()

            act_tree = ActView()
            act_tree.act_window = act_win
            act_tree.view, = View.search([
                    ('model', '=', step.main_model.model),
                    ('type', '=', 'tree'),],
                limit=1)
            act_tree.sequence = menu.sequence
            act_tree.save()

            act_form = ActView()
            act_form.act_window = act_win
            act_form.view, = View.search([
                    ('model', '=', step.main_model.model),
                    ('type', '=', 'form'),
                ], limit=1)
            act_form.sequence = menu.sequence
            act_form.save()

            step.menu_elem = menu

            step.save()
        

class StepMethodDesc(model.CoopSQL, model.CoopView):
    'Step Method Descriptor'
    '''
        This is a prototype of method (rule) which might be called anytime
        from a process.
        There might be child classes adding other fields needed for the
        calculate method.

        There are three core elements to this class :
            rule_kind : when is this method relevant ? It will be used by
                owner classes to decide which method to call when being ask for
                a specific kind of rule.
            get_data_pattern : before execution, the method might need some
                data from the calling process. This method returns a dict of
                model: [attributes] which are needed for calculation
            calculate : once you got the data, you're good to go !
    '''
    __name__ = 'process.step_method_desc'

    name = fields.Char('Name')

    # step is a backref to the step descriptor
    step = fields.Many2One(
        'process.step_desc',
        'Step',
        ondelete='CASCADE')

    rule_kind = fields.Selection(
        [
            ('step_over', 'Step Over'),
            ('before', 'Before Display'),
            ('check', 'Check Input'),
            ('update', 'Update Data'),
            ('validate', 'Validate Update'),
            ('after', 'After Update'),
        ],
        'Rule Kind',
        required=True)

    rule_type = fields.Selection(
        [
            ('code', 'Hardcoded Rule'),
            ('rule', 'Rule Engine'),
        ],
        'Rule Type',
        required=True,
    )

    rule_engine = fields.Many2One(
        'rule_engine',
        'Rule Engine',
        states={
            'invisible': Eval('rule_type') != 'rule',
        },
    )

    code = fields.Char(
        'Code',
        states={
            'invisible': Eval('rule_type') != 'code',
        },
    )

    # Should be used once the context selection works
    #code_selection = fields.Function(
        #fields.Selection(
            #'get_allowed_functions',
            #'Code',
            #states={
                #'invisible': Eval('rule_type') != 'code',
            #},
            #context={
                #'rule_kind': Eval('rule_kind')
            #},
        #),
        #'get_code_selection',
        #'set_code_selection',
    #)

    @classmethod
    def __setup__(cls):
        super(StepMethodDesc, cls).__setup__()
        cls.__rpc__['get_allowed_functions'] = RPC()

    @classmethod
    def get_allowed_functions(cls):
        good_model = Transaction().context.get('main_model')
        meth_type = Transaction().context.get('rule_kind')
        if not good_model or not meth_type:
            return []
        Model = Pool().get('ir.model')
        good_model = Model(good_model)
        model = Pool().get(good_model.model)
        res = []
        for elem in [getattr(model, x) for x in dir(model)
                if hasattr(getattr(model, x), 'def_meth')]:
            if elem.def_meth['meth_type'] == meth_type:
                res.append((elem.name, elem.def_meth['fancy_name']))

        return list(set(res))

    def get_code_selection(self, name):
        if (hasattr(self, 'code') and self.code):
            return self.code

    @classmethod
    def set_code_selection(cls, methods, name, value):
        cls.write(
            methods,
            {   
                'code': value
            })

    @classmethod
    def default_rule_type(cls):
        return 'code'

    def apply_meth(self, target):
        if not target:
            return
        if self.rule_type == 'code':
            good_meth = getattr(target, self.code)
            good_meth(target)
        elif self.rule_type == 'rule':
            #do_stuff
            # Basically, it should parse the code of the view to detect the
            # the presented fields in order to propose te fields in the
            # rule engine.
            pass


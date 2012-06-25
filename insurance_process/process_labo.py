# -*- coding: utf-8 -*-

# Needed for displaying and storing objects
from trytond.model import fields as fields

from trytond.modules.coop_utils import utils, CoopView, CoopSQL

# Needed for easy access to models
from trytond.pool import Pool

# Needed for Eval
from trytond.pyson import Eval, Not, Bool, Or

# Needed for accessing the Transaction singleton
from trytond.transaction import Transaction

from process import DependantState

__all__ = ['ProcessDesc', 'StepDesc', 'StepMethodDesc']

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


class ProcessDesc(CoopSQL, CoopView):
    '''
        Master Class for all processes, has a list of steps and
        knows the name of the model it is supposed to represent
    '''
    __name__ = 'ins_process.process_desc'

    # The user friendly name, we could forget it and use the coop_process_name
    # in its place.
    name = fields.Char('Process Name')

    # The list of steps. Ideally, there should be a way to order them
    # properly so that iteration on it would go the right way
    steps = fields.One2Many('ins_process.step_desc',
                            'process',
                            'Steps',
                # Here we set some data in the context so that it becomes
                # available when creating child records
                            context={
                        'parent_name': Eval('name'),
                                    })

    # This is a core field, it creates the link between the record and the
    # process it is supposed to represent.
    process_model = fields.Selection('get_process_model',
                                     'Process Model')

    # Here we create the list of tuple which will be available for selection.
    # Each tuple contains the model_name (i.e. 'ins_process.dummy_process')
    # associated with the process' user friendly name provided by
    # coop_process_name.
    @staticmethod
    def get_process_model():
        result = []
        for model_name, model in Pool().iterobject(type='wizard'):
            # Evil hack to check model's class inheritance
            if (hasattr(model, 'coop_process_name')
                and model.coop_process_name() != ''):
                result.append((model_name, model.coop_process_name()))
        return result

    # This method is called by the process itself, providing the process desc
    # as an argument, to get the process' first step desc and its model
    def get_first_step_desc(self):
        result = self.steps[0]
        return (result, result.step_model)

    # Here we got the current step, the current process, and we are asking for
    # the next one.
    def get_next_step(self, step):
        if step.sequence < len(self.steps):
            return self.steps[step.sequence]
        return step

    # idem for getting the previous step
    def get_prev_step(self, step):
        if step.sequence != 1:
            return self.steps[step.sequence - 2]
        return step


class StepDesc(CoopSQL, CoopView):
    '''
        Master Class for process steps.

        It has a reference to its ProcessDesc (process), knows the model name
        of the step it represents, and also has a list of additional rules
        which will be used.
    '''
    __name__ = 'ins_process.step_desc'

    # process is a backref to the process descriptor
    process = fields.Many2One('ins_process.process_desc',
                              'Process',
                              ondelete='CASCADE')

    # This is just a way to display the name of the process at creation time.
    # This field is a function field with a default value.
    process_name = fields.Function(fields.Char('Process Name'),
                                   'get_process_name')

    # sequence is rather important, it indicates the order of the step in the
    # list of steps of its process.
    sequence = fields.Integer('Sequence', required=True)

    # This is a core field, it creates the link between the record and the
    # step it is supposed to represent.
    step_model = fields.Selection('get_steps_model',
                                  'Step',
                                  states={
                            'invisible': Or(Bool(Eval('on_product_step')),
                                            Bool(Eval('virtual_step'))),
                            'required': Not(Or(Bool(Eval('on_product_step')),
                                            Bool(Eval('virtual_step')))),
                                    },
                                  depends=['on_product_step',
                                           'virtual_step'])

    # This is the list of methods which might be called when the step is asked
    # for client rules.
    methods = fields.One2Many('ins_process.step_method_desc',
                              'step',
                              'Methods',
                              states={
                                      'required': Bool(Eval('virtual_step')),
                                      },
                              depends=['virtual_step'])

    # Virtual_step makes the step 'virtual', that is without any form. It is
    # just a way to add user-defined methods between steps
    virtual_step = fields.Boolean('Virtual Step')

    # Here we give the user a possibility to define a step whos definition will
    # be found on the process instance product.
    # This must be done carefully, as we have to be sure that the process using
    # the state uses a product.
    on_product_step = fields.Boolean('On Product Step',
                                     states={
                                        'invisible': Bool(Eval('virtual_step'))
                                        },
                                     depends=['virtual_step'])

    # In the case the step is defined 'on product', we use the
    # product_step_name field to get the type of the step that we must look for
    # in the product step descriptions.
    product_step_name = fields.Selection('get_product_steps',
                                         'Product Step Name',
                                    #required=Eval('on_product_step'),
                                    states={
                                    'invisible': Or(Not(Bool(
                                                Eval('on_product_step'))),
                                                Bool(Eval('virtual_step'))),
                                    'required': Bool(Eval('on_product_step'))
                                            },
                                    depends=['on_product_step',
                                             'virtual_step'])

    # Step Name uses the get_step_name method to compute a user friendly name
    # from the step desc parameters
    step_name = fields.Function(fields.Char('Step Name'),
                                'get_step_name')

    button_next = fields.Function(fields.Boolean("'Next' button"),
                                  'get_button',
                                  setter='set_button')
    button_previous = fields.Function(fields.Boolean("'Previous' button"),
                                  'get_button',
                                  setter='set_button')
    button_check = fields.Function(fields.Boolean("'Check' button"),
                                  'get_button',
                                  setter='set_button')
    button_complete = fields.Function(fields.Boolean("'Complete' button"),
                                  'get_button',
                                  setter='set_button')
    button_cancel = fields.Function(fields.Boolean("'Cancel' button"),
                                  'get_button',
                                  setter='set_button')
    button_suspend = fields.Function(fields.Boolean("'Suspend' button"),
                                  'get_button',
                                  setter='set_button')

    button_default = fields.Function(fields.Selection(BUTTONS,
                                                      'Default Button'),
                                     'get_button',
                                     setter='set_button')

    buttons_storage = fields.Char('Buttons',
                                  states={'invisible': True})

    # This maps the 'sequence' column as the default order for step_descs
    @classmethod
    def __setup__(cls):
        super(StepDesc, cls).__setup__()
        cls._order.insert(0, ('sequence', 'ASC'))

    def get_button(self, name):
        buttons_str = self.buttons_storage
        idx = -1
        for button, _ in BUTTONS:
            idx += 1
            if not button in name:
                continue
            return bool(int(buttons_str[idx]))
        if 'button_default' in name:
            return BUTTONS[int(buttons_str[-1]) - 1]

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
                buttons_list[-1] = res
            else:
                if value:
                    res = '1'
                else:
                    res = '0'
                buttons_list[buttons_names.index(name)] = res
            buttons = ''.join(buttons_list)
            StepDesc.write([step], {
                            'buttons_storage': buttons,
                            })

    # Here we create the list of tuple which will be available for selection.
    # Each tuple contains the model_name (i.e. 'ins_process.dummy_step')
    # associated with the step's user friendly name provided by
    # coop_step_name.
    @staticmethod
    def get_steps_model():
        result = []
        for model_name, model in Pool().iterobject():
            # Evil hack to check model's class inheritance
            if (hasattr(model, 'coop_step_name')
                and model.coop_step_name() != ''):
                result.append((model_name, model.coop_step_name()))
        return result

    # This is our way of displaying the process' name. Unfortunately, this
    # method is not available while the process has not been stored (which
    # will provide an id). So...
    def get_process_name(self, name):
        return self.process.name

    # ... we set a default value for the function field, looking for the good
    # value in the context
    @staticmethod
    def default_process_name():
        res = Transaction().context.get('parent_name')
        return res

    # This method will be used by the processes to ask for the rules which
    # match the rule_kind and go through and call them.
    def get_appliable_rules(self, rule_kind):
        for rule in self.methods:
            if rule.rule_kind == rule_kind:
                yield rule

    # This method will be used to get the model of the state that is
    # associated to the step desc.
    def get_step_model(self, for_product):
        # Basic case :
        if not self.on_product_step and self.step_model != '':
            return self.step_model
        elif (self.on_product_step
            and self.product_step_name != ''
            and for_product):
            # Go look in for_product for the right step_model
            # return (lambda x:(x, x))(
                            # for_product.get_step(for_step.product_step_name))
            return 'ins_contract.subs_process.extension_life'
        else:
            return ''

    def get_step_name(self, name):
        if self.virtual_step == True:
            return 'Virtual Step'
        elif self.on_product_step == True:
            return self.product_step_name
        else:
            return self.step_model

    @staticmethod
    def get_product_steps():
        result = set()
        for cls in DependantState.__subclasses__():
            result.add((lambda x:(x, x))(cls.depends_on_state()))
        return list(result)

    @staticmethod
    def default_buttons_storage():
        return '0000000'


class StepMethodDesc(CoopSQL, CoopView):
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
    __name__ = 'ins_process.step_method_desc'

    name = fields.Char('Name')

    # step is a backref to the step descriptor
    step = fields.Many2One('ins_process.step_desc',
                           'Step',
                           ondelete='CASCADE')

    # METHOD TYPES are the possible context for which the method might be used.
    # Currently there are only two choices : step_over or check_step.
    # It will be used when the step is asked for methods matching a particular
    # rule_kind to decide which methods must be used.
    rule_kind = fields.Selection(METHOD_TYPES,
                                 'Rule Kind',
                                 required=True)

    def get_data_pattern(self):
        # This is an example of pattern which we could use to ask for the data
        # we need for calculation.
        # Hopefully, the process will look in its session for a contract
        # (matching 'ins_process.contract') and parse its fields.
        return {'ins_process.contract': ['start_date',
                                          'name']}

    # This method makes it work : It takes the rule to execute, the data it
    # needs, then return the result.
    def calculate(self, data):
        print 'Calculating %s' % self.name
        if self.rule_kind == '0_step_over':
            return False
        elif self.rule_kind == '2_check_step':
            return True

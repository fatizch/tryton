# -*- coding: utf-8 -*-

# Needed for displaying and storing objects
from trytond.model import ModelView, ModelSQL
from trytond.model import fields as fields

# Needed for easy access to models
from trytond.pool import Pool

# Needed for Eval
from trytond.pyson import Eval

#
from trytond.transaction import Transaction

# For now, just step_over and checks are customizable
METHOD_TYPES = [
                ('0_step_over', 'Must Step Over'),
                # ('1_before_step', 'Before Step Execution'),
                ('2_check_step', 'Step Validation'),
                # ('3_post_step', 'Step Completion')
                ]


class ProcessDesc(ModelSQL, ModelView):
    '''
        Master Class for all processes, has a list of steps and
        knows the name of the model it is supposed to represent
    '''
    _name = 'ins_process.process_desc'

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
                        'next_order': Eval('number_of_steps')
                                    })

    # This is a trick which allows us to keep track of how many steps are in
    # the list, maybe a 'count' method exists ?
    number_of_steps = fields.Integer('Number of fields',
                                     states={
                                             'invisible': True,
                                             },
                                     on_change_with=['steps']
                                      )

    # This is a core field, it creates the link between the record and the
    # process it is supposed to represent.
    process_model = fields.Selection('get_process_model',
                                     'Process Model')

    # Easy one : at first, there aren't any step in our process desc
    def default_number_of_steps(self):
        return 0

    # We makes number_of_steps increment each time the number of element in the
    # steps field change
    def on_change_with_number_of_steps(self, values):
        result = 0
        for step in values['steps']:
            result = result + 1
        return result

    # Here we create the list of tuple which will be available for selection.
    # Each tuple contains the model_name (i.e. 'ins_process.dummy_process')
    # associated with the process' user friendly name provided by
    # coop_process_name.
    def get_process_model(self):
        result = []
        for model_name, model in Pool().iterobject(type='wizard'):
            # Evil hack to check model's class inheritance
            if (hasattr(model, 'coop_process_name')
                and model.coop_process_name() != ''):
                result.append((model_name, model.coop_process_name()))
        return result

    # Testing some order changing through methods, does not seem to work well.
    def swap_top(self, process, for_step):
        cur_step = None
        for step in process.steps:
            if (step.order < for_step.order
                and
                ((not cur_step is None and step.order > cur_step.order)
                 or cur_step is None)):
                cur_step = step
                if cur_step.order == for_step.order - 1:
                    break
        if not cur_step is None:
            for_step.order = for_step.order - 1
            cur_step.order = cur_step.order + 1
            cur_step._model.write(cur_step.id, {'order': cur_step.order})
            for_step._model.write(for_step.id, {'order': for_step.order})

    # This method is called by the process itself, providing the process desc
    # as an argument, to get the process' first step desc and its model
    def get_first_step_desc(self, process):
        cur_min = -1
        cur_step = None
        # As it seems that there isn't any way to order the list properly,
        # we got to go through all the elements and look for the minimum order.
        for step in process.steps:
            if cur_step is None or (cur_min > step.order):
                cur_step = step
                cur_min = step.order
        return (cur_step, cur_step.step_model)

    # Here we got the current step, the current process, and we are asking for
    # the next one.
    def get_next_step(self, step, process):
        # Again, we have to go through the entire list to find what we are
        # looking for.
        for cur_step in process.steps:
            if cur_step.order == step.order + 1:
                return cur_step
        return step

    # idem for getting the previous step
    def get_prev_step(self, step, process):
        for cur_step in process.steps:
            if cur_step.order == step.order - 1:
                return cur_step
        return step

ProcessDesc()


class StepMethodDesc(ModelSQL, ModelView):
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
    _name = 'ins_process.step_method_desc'

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

    def get_data_pattern(self, rule):
        # This is an example of pattern which we could use to ask for the data
        # we need for calculation.
        # Hopefully, the process will look in its session for a contract
        # (matching 'ins_process.contract') and parse its fields.
        return {'ins_process.contract': ['effective_date',
                                          'name']}

    # This method makes it work : It takes the rule to execute, the data it
    # needs, then return the result.
    def calculate(self, rule, data):
        print 'Calculating %s' % rule.name
        if rule.rule_kind == '0_step_over':
            return False
        elif rule.rule_kind == '2_check_step':
            return True

StepMethodDesc()


class StepDesc(ModelSQL, ModelView):
    '''
        Master Class for process steps.

        It has a reference to its ProcessDesc (process), knows the model name
        of the step it represents, and also has a list of additional rules
        which will be used.
    '''
    _name = 'ins_process.step_desc'

    # process is a backref to the process descriptor
    process = fields.Many2One('ins_process.process_desc',
                              'Process',
                              ondelete='CASCADE')

    # This is just a way to display the name of the process at creation time.
    # This field is a function field with a default value.
    process_name = fields.Function(fields.Char('Process Name'),
                                   'get_process_name')

    # order is rather important, it indicates the order of the step in the
    # list of steps of its process.
    order = fields.Integer('Order')

    # This is a core field, it creates the link between the record and the
    # step it is supposed to represent.
    step_model = fields.Selection('get_steps_model',
                                  'Step',
                                  required=True)

    # This is the list of methods which might be called when the step is asked
    # for client rules.
    methods = fields.One2Many('ins_process.step_method_desc',
                              'step',
                              'Methods')

    # This is not necessary as long as 'go_up' do not work.
    # It allows the method to be called from the client when not in the step's
    # form view.
    def __init__(self):
        super(StepDesc, self).__init__()
        self._rpc.update({'go_up': True})
        self._buttons = {'go_up': {'invisible': Eval('order', 0) == 1}}

    # Testing some order changing through methods, does not seem to work well.
    @ModelView.button
    def go_up(self, ids):
        step_desc_obj = Pool().get('ins_process.step_desc')
        process_desc_obj = Pool().get('ins_process.process_desc')
        for step in step_desc_obj.browse(ids):
            process_desc_obj.swap_top(step.process, step)
        return True

    # When creating the object, we cannot access the process as it does not
    # have an idea yet. So we use the context, hoping that it was correctly
    # updated before displaying the form...
    def default_order(self):
        res = Transaction().context.get('next_order')
        if not res is None:
            return res + 1
        res = 0

    # Here we create the list of tuple which will be available for selection.
    # Each tuple contains the model_name (i.e. 'ins_process.dummy_step')
    # associated with the step's user friendly name provided by
    # coop_step_name.
    def get_steps_model(self):
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
    def get_process_name(self, ids, name):
        step_desc_obj = Pool().get('ins_process.step_desc')
        res = {}
        for step in step_desc_obj.browse(ids):
            res[step.id] = step.process.name
        return res

    # ... we set a default value for the function field, looking for the good
    # value in the context
    def default_process_name(self):
        res = Transaction().context.get('parent_name')
        return res

    # This method will be used by the processes to ask for the rules which
    # match the rule_kind and go through and call them.
    def get_appliable_rules(self, for_step, rule_kind):
        for rule in for_step.methods:
            if rule.rule_kind == rule_kind:
                yield rule

StepDesc()

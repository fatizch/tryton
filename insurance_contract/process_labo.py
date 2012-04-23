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
    _name = 'ins_contract.process_desc'

    name = fields.Char('Process Name')
    steps = fields.One2Many('ins_contract.step_desc',
                            'process',
                            'Steps',
                            context={
                        'parent_name': Eval('name'),
                        'next_order': Eval('number_of_steps')
                                    })
    number_of_steps = fields.Integer('Number of fields',
                                     states={
                                             'invisible': True,
                                             },
                                     on_change_with=['steps']
                                      )
    process_model = fields.Selection('get_process_model',
                                     'Process Model')

    def default_number_of_steps(self):
        return 0

    def on_change_with_number_of_steps(self, values):
        result = 0
        for step in values['steps']:
            result = result + 1
        return result

    def get_process_model(self):
        result = []
        for model_name, model in Pool().iterobject(type='wizard'):
            # Evil hack to check model's class inheritance
            if (hasattr(model, 'coop_process_name')
                and model.coop_process_name() != ''):
                result.append((model_name, model.coop_process_name()))
        return result

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

    def get_first_step_desc(self, process):
        cur_min = -1
        cur_step = None
        for step in process.steps:
            if cur_step is None or (cur_min > step.order):
                cur_step = step
                cur_min = step.order
        return (cur_step, cur_step.step_model)

    def get_next_step(self, step, process):
        for cur_step in process.steps:
            if cur_step.order == step.order + 1:
                return cur_step
        return step

ProcessDesc()


class StepMethodDesc(ModelSQL, ModelView):
    _name = 'ins_contract.step_method_desc'

    name = fields.Char('Name')
    step = fields.Many2One('ins_contract.step_desc',
                           'Step')
    rule_kind = fields.Selection(METHOD_TYPES,
                                 'Rule Kind')

    def get_data_pattern(self, rule):
        # This is an exemple of pattern which we could use to ask for the data
        # we need for calculation
        return {'ins_contract.contract': ['effective_date',
                                          'name']}

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
    _name = 'ins_contract.step_desc'

    process = fields.Many2One('ins_contract.process_desc',
                              'Process',
                              ondelete='CASCADE')
    process_name = fields.Function(fields.Char('Process Name'),
                                   'get_process_name')
    order = fields.Integer('Order')
    step_model = fields.Selection('get_steps_model',
                                  'Step',
                                  required=True)
    methods = fields.One2Many('ins_contract.step_method_desc',
                              'step',
                              'Methods')

    def __init__(self):
        super(StepDesc, self).__init__()
        self._rpc.update({'go_up': True})

    def go_up(self, ids):
        step_desc_obj = Pool().get('ins_contract.step_desc')
        process_desc_obj = Pool().get('ins_contract.process_desc')
        for step in step_desc_obj.browse(ids):
            process_desc_obj.swap_top(step.process, step)
        return True

    def default_order(self):
        res = Transaction().context.get('next_order')
        if not res is None:
            return res + 1

    def get_steps_model(self):
        result = []
        for model_name, model in Pool().iterobject():
            # Evil hack to check model's class inheritance
            if (hasattr(model, 'coop_step_name')
                and model.coop_step_name() != ''):
                result.append((model_name, model.coop_step_name()))
        return result

    def get_process_name(self, ids, name):
        step_desc_obj = Pool().get('ins_contract.step_desc')
        res = {}
        for step in step_desc_obj.browse(ids):
            res[step.id] = step.process.name

    def default_process_name(self):
        res = Transaction().context.get('parent_name')
        return res

    def get_appliable_rules(self, for_step, rule_kind):
        for rule in for_step.methods:
            if rule.rule_kind == rule_kind:
                yield rule

StepDesc()

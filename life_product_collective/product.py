from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.coop_utils import utils, fields

__all__ = [
    'GroupPricingRule',
    'GroupPricingComponent',
]


class GroupPricingRule():
    'Pricing Rule'

    __name__ = 'ins_product.pricing_rule'
    __metaclass__ = PoolMeta

    college = fields.Many2One('party.college', 'College',
        on_change=['college', 'component'])

    def on_change_college(self):
        if not self.college:
            return {'components': []}
        basic_element = utils.create_inst_with_default_val(self.__class__,
            'components')[0]
        res = []
        for tranche in self.college.tranches:
            cur_component = basic_element.copy()
            cur_component['tranche'] = tranche.id
            cur_component['code'] = '%s_%s' % (self.college.code, tranche.code)
            res.append(cur_component)
        return {'components': {'add': res}}


class GroupPricingComponent():
    'Pricing Component'

    __name__ = 'ins_collective.pricing_component'
    __metaclass__ = PoolMeta

    rate = fields.Numeric('Rate',
        help='Value between 0 and 100',
        states={
            'invisible': Eval('config_kind') != 'simple',
        }, depends=['config_kind'])
    contribution_base = fields.Numeric('Contribution Base',
        help='Value between 0 and 100',
        states={
            'invisible': Eval('config_kind') != 'simple',
        }, depends=['config_kind'])

    @staticmethod
    def default_contribution_base():
        return 100

    def get_amount(self, args):
        #this function take a dictionary as argument, with the 'date' for
        #calculation date and either the whole employee salary in 'salary'
        #or the payroll of the company, tranche by tranche, with the tranche
        #code as the dictionary key
        #example 1 : {'salary':50000}
        #example 2 : {'TA':1578000, 'TB': 2500000, 'TC'.....}
        errors = []
        if self.kind != 'simple':
            return super(GroupPricingComponent, self).get_amount(args)
        if 'date' in args:
            at_date = args['date']
        #Either we have the payroll for all the company for the good tranche,
        #or we have the whole employee salary, that we need to split in salary
        if self.tranche.code in args or 'salary' in args:
            if self.tranche.code in args:
                salary_tranche = args[self.tranche.code]
            else:
                salary_tranche = self.tranche.get_tranche_value(
                    args['tranche'], at_date)
            amount = (self.fixed_value
                + (self.rate / 100
                   * self.contribution_base / 100
                   * salary_tranche
                   ))
        else:
            errors.append('missing_param_salary_or_payroll')
            amount = 0
        return amount, errors

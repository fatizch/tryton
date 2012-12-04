#-*- coding:utf-8 -*
import copy

from trytond.pool import PoolMeta
from trytond.model import fields
from trytond.pyson import Eval

from trytond.modules.coop_utils import utils
from trytond.modules.life_product import LifeCoverage
__all__ = [
    'GroupLifeCoverage',
    'GroupPricingData',
    'GroupPriceCalculator',
]


class GroupLifeCoverage(LifeCoverage):
    'Coverage'

    __name__ = 'ins_collective.coverage'


class GroupPricingData():
    'Pricing Component'

    __name__ = 'ins_collective.pricing_data'
    __metaclass__ = PoolMeta

    rate = fields.Numeric('Rate',
        help='Value between 0 and 100',
        states={
            'invisible': Eval('config_kind') != 'simple',
        },
        depends=['config_kind'],
        )
    contribution_base = fields.Numeric('Contribution Base',
        help='Value between 0 and 100',
        states={
            'invisible': Eval('config_kind') != 'simple',
        },
        depends=['config_kind'],
        )
    tranche = fields.Many2One('tranche.tranche', 'Tranche',
        states={
            'required': Eval('config_kind') == 'simple',
            'invisible': Eval('config_kind') != 'simple',
        },
        depends=['config_kind'],
        )

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
            return super(GroupPricingData, self).get_amount(args)
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


class GroupPriceCalculator():
    'Price Calculator'

    __name__ = 'ins_collective.pricing_calculator'
    __metaclass__ = PoolMeta

    college = fields.Many2One('party.college', 'College')
    tranches = fields.Function(fields.Char('Tranches',
            on_change_with=['college']),
        'on_change_with_tranches')

    @classmethod
    def __setup__(cls):
        super(GroupPriceCalculator, cls).__setup__()
        cls.data = copy.copy(cls.data)
#        if not cls.data.context:
#            cls.data.context = {}
#        cls.data.context['tranches'] = Eval('college', {}).get('code')
#        if not cls.data.depends:
#            cls.data.depends = []
#        utils.append_inexisting(cls.data.depends, 'college')
#        if not cls.data.states:
#            cls.data.states = {}
#        cls.data.states['readonly'] = ~Eval('college')
#        cls.data.domain = []
        cls.data.domain.append(
            (
                'tranche.id',
                'in',
                Eval('_parent_calculator', {}).get('tranches')
            )
        )
#        cls.data.depends = ['tranches']

    def on_change_with_tranches(self):
        tranches = []
        if self.college:
            tranches = [x.id for x in self.college.tranches]
        print tranches
        return str(tranches)

    @staticmethod
    def default_key():
        return 'sub_price'

import copy

from trytond.pool import PoolMeta
from trytond.pyson import Eval, Or, And, Bool
from trytond.modules.coop_utils import fields, utils, model
from trytond.modules.insurance_product import BusinessRuleRoot

__metaclass__ = PoolMeta

__all__ = [
    'CashValueRule',
    'Product',
    'Coverage',
    ]


class CashValueRule(BusinessRuleRoot, model.CoopSQL):
    'Cash Value Rule'

    __name__ = 'cash_value.cash_value_rule'

    saving_account = fields.Many2One('account.account', 'saving_account')

    def give_me_computed_cash_values(self, args):
        return self.computation_rule.execute(args)

    def give_me_actualized_cash_value(self, args):
        return self.get_rule_result(args)

    @classmethod
    def default_kind(cls):
        return 'advanced'

    def give_me_saving_account(self, args):
        return self.saving_account


class Product:
    'Product'

    __name__ = 'offered.product'

    is_cash_value = fields.Function(
        fields.Boolean('Is Cash Value', states={'invisible': True}),
        'get_is_cash_value_product')

    def get_is_cash_value_product(self, name):
        for coverage in self.coverages:
            if coverage.is_cash_value:
                return True
        return False


class Coverage:
    'Coverage'

    __name__ = 'offered.option.description'

    is_cash_value = fields.Function(
        fields.Boolean('Is Cash Value', states={'invisible': True}),
        'get_is_cash_value_coverage')
    cash_value_rules = fields.One2Many('cash_value.cash_value_rule', 'offered',
        'Cash Value Rules')

    @classmethod
    def __setup__(cls):
        super(Coverage, cls).__setup__()
        cls.family = copy.copy(cls.family)
        if not cls.family.selection:
            cls.family.selection = []
        utils.append_inexisting(cls.family.selection,
            ('cash_value', 'Cash Value'))
        cls.coverage_amount_rules = copy.copy(cls.coverage_amount_rules)
        cls.coverage_amount_rules.states['invisible'] = And(
            cls.coverage_amount_rules.states['invisible'],
            Or(Bool(Eval('is_package')), Eval('family') != 'cash_value'))

    def get_is_cash_value_coverage(self, name):
        return self.family == 'cash_value'

    def give_me_actualized_cash_value(self, args):
        return self.get_result('actualized_cash_value', args,
            kind='cash_value')

    def give_me_saving_account(self, args):
        return self.get_result('saving_account', args, kind='cash_value')

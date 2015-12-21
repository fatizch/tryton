from trytond.pool import PoolMeta
from trytond.modules.cog_utils import fields, model
from trytond.modules.offered_insurance import BusinessRuleRoot

__metaclass__ = PoolMeta

__all__ = [
    'CashValueRule',
    'Product',
    'OptionDescription',
    ]


class CashValueRule(BusinessRuleRoot, model.CoopSQL):
    'Cash Value Rule'

    __name__ = 'cash_value.cash_value_rule'

    saving_account = fields.Many2One('account.account', 'saving_account',
        ondelete='RESTRICT')

    def give_me_computed_cash_values(self, args):
        return self.computation_rule.execute(args)

    def give_me_actualized_cash_value(self, args):
        return self.get_rule_result(args)

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


class OptionDescription:
    'OptionDescription'

    __name__ = 'offered.option.description'

    is_cash_value = fields.Function(
        fields.Boolean('Is Cash Value', states={'invisible': True}),
        'get_is_cash_value_coverage')
    cash_value_rules = fields.One2Many('cash_value.cash_value_rule', 'offered',
        'Cash Value Rules', delete_missing=True)

    @classmethod
    def __setup__(cls):
        super(OptionDescription, cls).__setup__()
        cls.family.selection.append(('cash_value', 'Cash Value'))

    def get_is_cash_value_coverage(self, name):
        return self.family == 'cash_value'

    def give_me_actualized_cash_value(self, args):
        return self.get_result('actualized_cash_value', args,
            kind='cash_value')

    def give_me_saving_account(self, args):
        return self.get_result('saving_account', args, kind='cash_value')

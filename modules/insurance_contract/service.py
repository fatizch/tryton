from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.coop_utils import model, fields
from trytond.modules.coop_currency import ModelCurrency
from trytond.modules.coop_currency.currency import DEF_CUR_DIG

__metaclass__ = PoolMeta
__all__ = [
    'ContractService',
    'Expense',
    ]


class ContractService:
    __name__ = 'contract.service'

    expenses = fields.One2Many('expense', 'delivered_service', 'Expenses')

    def get_expense(self, code, currency):
        for expense in self.expenses:
            if (expense.kind and expense.kind.code == code
                    and expense.currency == currency):
                return expense.amount

    def get_total_expense(self, currency):
        res = 0
        for expense in self.expenses:
            if expense.currency == currency:
                res += expense.amount
        return res


class Expense(model.CoopSQL, model.CoopView, ModelCurrency):
    'Expense'

    __name__ = 'expense'

    delivered_service = fields.Many2One('contract.service', 'Contract Service',
        ondelete='CASCADE')
    kind = fields.Many2One('expense.kind', 'Kind')
    amount = fields.Numeric('Amount', required=True, digits=(
            16, Eval('currency_digits', DEF_CUR_DIG)),
        depends=['currency_digits'])

    @classmethod
    def default_currency(cls):
        return ModelCurrency.default_currency()

    def get_currency_digits(self, name):
        if hasattr(self, 'currency') and self.currency:
            return self.currency.digits

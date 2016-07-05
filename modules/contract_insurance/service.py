# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.cog_utils import model, fields
from trytond.modules.currency_cog import ModelCurrency
from trytond.modules.currency_cog.currency import DEF_CUR_DIG

__metaclass__ = PoolMeta
__all__ = [
    'ContractService',
    'Expense',
    ]


class ContractService:
    __name__ = 'contract.service'

    expenses = fields.One2Many('expense', 'service', 'Expenses',
        delete_missing=True)

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

    service = fields.Many2One('contract.service', 'Contract Service',
        ondelete='CASCADE', required=True, select=True)
    kind = fields.Many2One('expense.kind', 'Kind', ondelete='RESTRICT')
    amount = fields.Numeric('Amount', required=True, digits=(
            16, Eval('currency_digits', DEF_CUR_DIG)),
        depends=['currency_digits'])

    @classmethod
    def default_currency(cls):
        return ModelCurrency.default_currency()

    def get_currency_digits(self, name):
        if hasattr(self, 'currency') and self.currency:
            return self.currency.digits

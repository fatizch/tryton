# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.modules.coog_core import fields

__all__ = [
    'Loan',
    ]


class Loan:
    __metaclass__ = PoolMeta
    __name__ = 'loan'

    average_premium_rate = fields.Function(
        fields.Numeric('Average Premium Rate', digits=(6, 4)),
        'get_average_premium_rate')
    base_premium_amount = fields.Function(
        fields.Numeric('Base Premium Amount', digits=(16, 2)),
        'get_average_premium_rate')
    base_fee_amount = fields.Function(
        fields.Numeric('Base Fee Amount', digits=(16, 2)),
        'get_average_premium_rate')
    average_fee_rate = fields.Function(
        fields.Numeric('Average Fee Rate', digits=(6, 4)),
        'get_average_premium_rate')

    @classmethod
    def get_average_premium_rate(cls, loans, names, contract=None):
        if not contract:
            contract_id = Transaction().context.get('contract', None)
            if contract_id:
                contract = Pool().get('contract')(contract_id)
            else:
                return {name: {x.id: None for x in loans} for name in names}
        field_values = {'average_premium_rate': {}, 'base_premium_amount': {},
            'base_fee_amount': {}, 'average_fee_rate': {}}
        rule = contract.product.average_loan_premium_rule
        for loan in loans:
            vals = rule.calculate_average_premium_for_contract(loan, contract)
            field_values['base_premium_amount'][loan.id] = vals[0] or 0
            field_values['average_premium_rate'][loan.id] = vals[1] or 0
            field_values['base_fee_amount'][loan.id] = vals[2] or 0
            field_values['average_fee_rate'][loan.id] = vals[3] or 0

        return field_values

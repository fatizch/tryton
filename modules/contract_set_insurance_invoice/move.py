# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

__all__ = [
    'PartyBalance',
    ]


class PartyBalance:
    __metaclass__ = PoolMeta
    __name__ = 'account.party_balance'

    def invoices_report_for_balance(self, contract):
        if not contract.contract_set:
            return super(PartyBalance, self).invoices_report_for_balance(
                    contract)
        return contract.contract_set.invoices_report()[0]

# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool

__metaclass__ = PoolMeta

__all__ = [
    'MoveLine',
    ]


class MoveLine:
    __name__ = 'account.move.line'

    def new_payment(self, journal, kind, amount):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        payment = super(MoveLine, self).new_payment(journal, kind, amount)
        if kind == 'payable':
            return payment
        if (self.origin and isinstance(self.origin, Invoice) and
                self.origin.sepa_mandate):
            payment['sepa_mandate'] = self.origin.sepa_mandate.id
        billing_info = self.contract.billing_information \
            if self.contract else None
        if billing_info:
            payment['date'] = billing_info.get_direct_debit_planned_date(self) \
                or payment['date']
        return payment

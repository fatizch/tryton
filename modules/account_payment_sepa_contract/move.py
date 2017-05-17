# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
__metaclass__ = PoolMeta

__all__ = [
    'MoveLine',
    ]


class MoveLine:
    __name__ = 'account.move.line'

    def init_payment_information(self, journal, kind, amount, payment):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        mandate = None
        if kind == 'receivable':
            if (self.origin and isinstance(self.origin, Invoice) and
                    self.origin.sepa_mandate):
                mandate = self.origin.sepa_mandate
            billing_info = self.contract.billing_information \
                if self.contract else None
            if billing_info:
                payment['date'] = \
                    billing_info.get_direct_debit_planned_date(self) \
                    or payment['date']
        if kind == 'payable' and self.contract:
            with Transaction().set_context(
                    contract_revision_date=payment['date']):
                mandate = self.contract.billing_information.sepa_mandate \
                    if self.contract.billing_information else None
        if mandate:
            payment['sepa_mandate'] = mandate.id
            payment['bank_account'] = mandate.account_number.account.id
        return super(MoveLine, self).init_payment_information(journal, kind,
            amount, payment)

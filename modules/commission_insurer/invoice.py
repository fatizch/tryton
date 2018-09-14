# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool

from trytond.modules.coog_core import utils


__all__ = [
    'Invoice',
    ]


class Invoice:
    __metaclass__ = PoolMeta
    __name__ = 'account.invoice'

    @classmethod
    def __setup__(cls):
        super(Invoice, cls).__setup__()
        cls.business_kind.selection += [
            ('all_insurer_invoices', 'All Insurer Invoices'),
            ]

    @classmethod
    def get_commission_insurer_invoice_types(cls):
        return super(Invoice, cls).get_commission_insurer_invoice_types() + [
            'all_insurer_invoices']

    def _get_move_line(self, date, amount):
        insurer_journal = None
        line = super(Invoice, self)._get_move_line(date, amount)
        configuration = Pool().get('account.configuration').get_singleton()
        if configuration is not None:
            insurer_journal = configuration.insurer_payment_journal
        if (getattr(self, 'business_kind', None) in ('insurer_invoice',
                    'all_insurer_invoices') and
                self.type == 'in' and self.total_amount > 0
                and insurer_journal is not None):
            line.payment_date = line.maturity_date or utils.today()
        return line

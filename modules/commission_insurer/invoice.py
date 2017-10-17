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

    def _get_move_line(self, date, amount):
        insurer_journal = None
        line = super(Invoice, self)._get_move_line(date, amount)
        configuration = Pool().get('account.configuration').get_singleton()
        if configuration is not None:
            insurer_journal = configuration.insurer_payment_journal
        if (getattr(self, 'business_kind', None) == 'insurer_invoice' and
                self.type == 'in' and self.total_amount > 0):
            if ((self.business_kind == 'insurer_invoice') and
            (insurer_journal is not None)):
                line.payment_date = line.maturity_date or utils.today()
        return line

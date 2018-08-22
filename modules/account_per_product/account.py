# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction

from trytond.modules.coog_core import fields

__all__ = [
    'AgedBalanceContext',
    'AgedBalanceReport',
    ]


class AgedBalanceContext:
    __metaclass__ = PoolMeta
    __name__ = 'account.aged_balance.context'

    product = fields.Many2One('offered.product', 'Product')


class AgedBalanceReport:
    __metaclass__ = PoolMeta
    __name__ = 'account.aged_balance'

    @classmethod
    def get_context(cls, records, data):
        Product = Pool().get('offered.product')
        report_context = super(AgedBalanceReport, cls).get_context(records,
            data)
        product = Transaction().context.get('product')
        report_context['product'] = Product(product) if product else None
        return report_context

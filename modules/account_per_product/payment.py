# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import PoolMeta

from trytond.modules.coog_core import fields


__all__ = [
    'Journal',
    ]


class Journal:
    __metaclass__ = PoolMeta
    __name__ = 'account.payment.journal'

    product = fields.Function(
        fields.Many2One('offered.product', 'Product'),
        'get_product')
    products = fields.One2Many('offered.product', 'payment_journal', 'Products'
        )

    def get_product(self, name):
        return self.products[0].id if self.products else None

    @classmethod
    def _export_skips(cls):
        return super(Journal, cls)._export_skips() | {'products'}

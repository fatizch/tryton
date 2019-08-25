# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import PoolMeta

from trytond.modules.coog_core import fields


__all__ = [
    'Journal',
    'Payment',
    ]


class Journal(metaclass=PoolMeta):
    __name__ = 'account.payment.journal'

    product = fields.Function(
        fields.Many2One('offered.product', 'Product'),
        'get_product')
    products = fields.One2Many('offered.product', 'sepa_payment_journal',
        'Products')

    @classmethod
    def copy(cls, instances, default=None):
        default = default.copy() if default else {}
        default.setdefault('products', None)
        return super(Journal, cls).copy(instances, default=default)

    def get_product(self, name):
        return self.products[0].id if self.products else None

    @classmethod
    def _export_skips(cls):
        return super(Journal, cls)._export_skips() | {'products'}


class Payment(metaclass=PoolMeta):
    __name__ = 'account.payment'

    def create_clearing_move(self, date=None):
        move = super(Payment, self).create_clearing_move(date)
        if move:
            move.product = self.line.move.product
        return move

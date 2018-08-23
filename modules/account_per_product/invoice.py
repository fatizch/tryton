# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from __future__ import unicode_literals

from trytond.pool import PoolMeta
from trytond.modules.coog_core import fields

__all__ = [
    'Invoice',
    ]


class Invoice:
    __metaclass__ = PoolMeta
    __name__ = 'account.invoice'

    product = fields.Many2One('offered.product', 'Product',
        ondelete='RESTRICT', readonly=True)

    @classmethod
    def create_reset_moves(cls, lines_per_invoice):
        moves = super(Invoice, cls).create_reset_moves(lines_per_invoice)
        for move in moves:
            move.product = move.origin.product
        return moves

    def get_move(self):
        move = super(Invoice, self).get_move()
        move.product = self.product
        return move

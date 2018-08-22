# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.coog_core import fields

__all__ = [
    'Statement',
    'Line',
    ]


class Statement:
    __metaclass__ = PoolMeta
    __name__ = 'account.statement'

    product = fields.Many2One('offered.product', 'Product',
        ondelete='RESTRICT', required=True,
        states={'readonly': Eval('state') != 'draft'}, depends=['state'])

    def _get_move(self, key):
        move = super(Statement, self)._get_move(key)
        move.product = self.product
        return move


class Line:
    __metaclass__ = PoolMeta
    __name__ = 'account.statement.line'

    @classmethod
    def __setup__(cls):
        super(Line, cls).__setup__()
        cls.invoice.domain.append(('product', '=',
                Eval('_parent_statement', {}).get('product', None)))
        cls.contract.domain.append(('product', '=',
                Eval('_parent_statement', {}).get('product', None)))

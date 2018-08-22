# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval
from trytond.transaction import Transaction

from trytond.modules.coog_core import fields

__all__ = [
    'Move',
    'MoveLine',
    'Reconcile',
    'ReconcileShow',
    'MoveTemplate',
    'MoveTemplateKeyword',
    'MoveLineTemplate',
    ]


class Move:
    __name__ = 'account.move'
    __metaclass__ = PoolMeta

    product = fields.Many2One('offered.product', 'Product',
        ondelete='RESTRICT', states={
            'readonly': Eval('state') == 'posted',
        }, depends=['state'], required=True)

    @classmethod
    def create(cls, vlist):
        vlist = [v.copy() for v in vlist]
        for vals in vlist:
            if not vals.get('product', None):
                if Transaction().context.get('product', None):
                    vals['product'] = Transaction().context.get('product')
        moves = super(Move, cls).create(vlist)
        return moves


class MoveLine:
    __metaclass__ = PoolMeta
    __name__ = 'account.move.line'

    product = fields.Function(fields.Many2One('offered.product',
        'Product'), 'get_move_field', searcher='search_move_field')

    def get_query_get_where_clause(cls, table, where):
        product = Transaction().context.get('product')
        if product:
            move = Pool().get('account.move').__table__()
            where &= (move.product == product)
        return where

    @classmethod
    def reconcile(cls, *lines_list, **writeoff):
        reconciliations = []
        for lines in lines_list:
            products = list({l.product for l in lines})
            if len(products) == 1:
                with Transaction().set_context(product=products[0].id):
                    reconciliations += super(MoveLine, cls).reconcile(lines,
                        **writeoff)
            else:
                reconciliations += super(MoveLine, cls).reconcile(lines,
                    **writeoff)
        return reconciliations

    def split(self, amount_to_split, journal=None):
        move = super(MoveLine, self).split(amount_to_split, journal)
        if move and self.product:
            move.product = self.product
        return move


class Reconcile:
    __metaclass__ = PoolMeta
    __name__ = 'account.reconcile'

    def transition_reconcile(self):
        products = list({l.product for l in self.show.lines})
        product = self.show.product
        if len(products) == 1:
            product = products[0]
        if product:
            with Transaction().set_context(product=products[0].id):
                return super(Reconcile, self).transition_reconcile()
        return super(Reconcile, self).transition_reconcile()


class ReconcileShow:
    __metaclass__ = PoolMeta
    __name__ = 'account.reconcile.show'

    product = fields.Many2One('offered.product', 'Product', required=True)


class MoveTemplate:
    __metaclass__ = PoolMeta
    __name__ = 'account.move.template'

    def get_move(self, values):
        move = super(MoveTemplate, self).get_move(values)
        move.product = move.lines[0].product
        return move


class MoveTemplateKeyword:
    __metaclass__ = PoolMeta
    __name__ = 'account.move.template.keyword'

    @classmethod
    def __setup__(cls):
        super(MoveTemplateKeyword, cls).__setup__()
        cls.type_.selection.append(('product', 'Product'))

    def _get_field_product(self):
        return {
            'type': 'many2one',
            'relation': 'offered.product',
            }

    def _format_product(self, lang, value):
        Product = Pool().get('offered.product')
        if value:
            return Product(value).rec_name
        else:
            return ''


class MoveLineTemplate:
    __metaclass__ = PoolMeta
    __name__ = 'account.move.line.template'

    product = fields.Char('Product', required=True)

    def get_line(self, values):
        line = super(MoveLineTemplate, self).get_line(values)
        line.product = values.get(self.product)
        return line

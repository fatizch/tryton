# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction

from trytond.modules.coog_core import fields

__all__ = [
    'Invoice',
    ]


class Invoice:
    __metaclass__ = PoolMeta
    __name__ = 'account.invoice'

    portfolio = fields.Function(
        fields.Many2One('distribution.network', 'Portfolio'),
        'get_portfolio', searcher='search_portfolio')

    @fields.depends('party')
    def on_change_with_portfolio(self, name=None):
        return self.party.portfolio.id if self.party and \
            self.party.portfolio else None

    @classmethod
    def get_portfolio(cls, instances, name):
        res = {}
        cursor = Transaction().connection.cursor()
        party = Pool().get('party.party').__table__()
        invoice = cls.__table__()

        cursor.execute(*
            invoice.join(party, 'LEFT OUTER',
                condition=(invoice.party == party.id)).select(
                invoice.id, party.portfolio,
                where=(invoice.id.in_([x.id for x in instances]))))
        for invoice_id, value in cursor.fetchall():
            res[invoice_id] = value
        return res

    @classmethod
    def search_portfolio(cls, name, clause):
        return [('party.portfolio',) + tuple(clause[1:])]

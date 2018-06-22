# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction

from trytond.modules.coog_core import fields

__all__ = [
    'LineGroup',
    ]


class LineGroup:
    __metaclass__ = PoolMeta
    __name__ = 'account.statement.line.group'

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
        statement = cls.__table__()

        cursor.execute(*
            statement.join(party, 'LEFT OUTER',
                condition=(statement.party == party.id)).select(
                statement.id, party.portfolio,
                where=(statement.id.in_([x.id for x in instances]))))
        for statement_id, value in cursor.fetchall():
            res[statement_id] = value
        return res

    @classmethod
    def search_portfolio(cls, name, clause):
        return [('party.portfolio',) + tuple(clause[1:])]

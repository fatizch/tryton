# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction

from trytond.modules.coog_core import fields

__all__ = [
    'Line',
    ]


class Line:
    __metaclass__ = PoolMeta
    __name__ = 'account.move.line'

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
        line = cls.__table__()

        cursor.execute(*
            line.join(party, 'LEFT OUTER',
                condition=(line.party == party.id)).select(
                line.id, party.portfolio,
                where=(line.id.in_([x.id for x in instances]))))
        for line_id, value in cursor.fetchall():
            res[line_id] = value
        return res

    @classmethod
    def search_portfolio(cls, name, clause):
        if clause[1] == '=' and not clause[2]:
            return['OR',
                [('party.portfolio', '=', None)],
                [('party', '=', None)]]
        return [('party.portfolio',) + tuple(clause[1:])]

# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction

from trytond.modules.coog_core import fields

__all__ = [
    'Claim',
    ]


class Claim:
    __metaclass__ = PoolMeta
    __name__ = 'claim'

    portfolio = fields.Function(
        fields.Many2One('distribution.network', 'Portfolio'),
        'get_portfolio', searcher='search_portfolio')

    @fields.depends('claimant')
    def on_change_with_portfolio(self, name=None):
        return self.claimant.portfolio.id if self.claimant and \
            self.claimant.portfolio else None

    @classmethod
    def get_portfolio(cls, instances, name):
        res = {}
        cursor = Transaction().connection.cursor()
        party = Pool().get('party.party').__table__()
        claim = cls.__table__()

        cursor.execute(*
            claim.join(party, 'LEFT OUTER',
                condition=(claim.claimant == party.id)).select(
                claim.id, party.portfolio,
                where=(claim.id.in_([x.id for x in instances]))))
        for claim_id, value in cursor.fetchall():
            res[claim_id] = value
        return res

    @classmethod
    def search_portfolio(cls, name, clause):
        return [('claimant.portfolio',) + tuple(clause[1:])]


class Loss:
    __metaclass__ = PoolMeta
    __name__ = 'claim.loss'

    portfolio = fields.Function(
        fields.Many2One('distribution.network', 'Portfolio'),
        'get_portfolio', searcher='search_portfolio')

    @fields.depends('claimant')
    def on_change_with_portfolio(self, name=None):
        return self.claim.portfolio.id if self.claim and \
            self.claim.portfolio else None

    @classmethod
    def get_portfolio(cls, instances, name):
        res = {}
        cursor = Transaction().connection.cursor()
        party = Pool().get('party.party').__table__()
        claim = Pool().get('claim').__table__()
        loss = cls.__table__()

        cursor.execute(*
            claim.join(party, 'LEFT OUTER',
                condition=(claim.claimant == party.id)).join(
                loss, condition=(loss.claim == claim.id)).select(
                loss.id, party.portfolio,
                where=(loss.id.in_([x.id for x in instances]))))
        for loss_id, value in cursor.fetchall():
            res[loss_id] = value
        return res

    @classmethod
    def search_portfolio(cls, name, clause):
        return [('claim.claimant.portfolio',) + tuple(clause[1:])]

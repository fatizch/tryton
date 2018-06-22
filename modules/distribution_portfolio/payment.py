# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction

from trytond.modules.coog_core import fields

__all__ = [
    'Payment',
    'Mandate',
    'MergedPayment',
    ]


class Payment:
    __metaclass__ = PoolMeta
    __name__ = 'account.payment'

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
        payment = cls.__table__()

        cursor.execute(*
            payment.join(party, 'LEFT OUTER',
                condition=(payment.party == party.id)).select(
                payment.id, party.portfolio,
                where=(payment.id.in_([x.id for x in instances]))))
        for payment_id, value in cursor.fetchall():
            res[payment_id] = value
        return res

    @classmethod
    def search_portfolio(cls, name, clause):
        return [('party.portfolio',) + tuple(clause[1:])]


class Mandate:
    __metaclass__ = PoolMeta
    __name__ = 'account.payment.sepa.mandate'

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
        mandate = cls.__table__()

        cursor.execute(*
            mandate.join(party, 'LEFT OUTER',
                condition=(mandate.party == party.id)).select(
                mandate.id, party.portfolio,
                where=(mandate.id.in_([x.id for x in instances]))))
        for mandate_id, value in cursor.fetchall():
            res[mandate_id] = value
        return res

    @classmethod
    def search_portfolio(cls, name, clause):
        return [('party.portfolio',) + tuple(clause[1:])]


class MergedPayment:
    __metaclass__ = PoolMeta
    __name__ = 'account.payment.merged'

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
        merged_payment = cls.__table__()

        cursor.execute(*
            merged_payment.join(party, 'LEFT OUTER',
                condition=(merged_payment.party == party.id)).select(
                merged_payment.id, party.portfolio,
                where=(merged_payment.id.in_([x.id for x in instances]))))
        for merged_payment_id, value in cursor.fetchall():
            res[merged_payment_id] = value
        return res

    @classmethod
    def search_portfolio(cls, name, clause):
        return [('party.portfolio',) + tuple(clause[1:])]

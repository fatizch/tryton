# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction

from trytond.modules.coog_core import fields

__all__ = [
    'Party',
    'ContactMechanism',
    'PartyRelationAll',
    ]


class Party:
    __metaclass__ = PoolMeta
    __name__ = 'party.party'

    portfolio = fields.Many2One('distribution.network', 'Portfolio',
        ondelete='RESTRICT', domain=[('is_portfolio', '=', True)], select=True)

    @staticmethod
    def default_portfolio():
        pool = Pool()
        user = Transaction().user
        if user:
            User = pool.get('res.user')
            dist_network = User(user).dist_network
            if dist_network:
                if dist_network.portfolio:
                    return dist_network.portfolio.id
        Configuration = pool.get('party.configuration')
        config = Configuration(1)
        if config.default_portfolio:
            return config.default_portfolio.id


class ContactMechanism:
    __metaclass__ = PoolMeta
    __name__ = 'party.contact_mechanism'

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
        contact_mechanism = cls.__table__()

        cursor.execute(*
            contact_mechanism.join(party, 'LEFT OUTER',
                condition=(contact_mechanism.party == party.id)).select(
                contact_mechanism.id, party.portfolio,
                where=(contact_mechanism.id.in_([x.id for x in instances]))))
        for contact_mechanism_id, value in cursor.fetchall():
            res[contact_mechanism_id] = value
        return res

    @classmethod
    def search_portfolio(cls, name, clause):
        return [('party.portfolio',) + tuple(clause[1:])]


class PartyRelationAll:
    __metaclass__ = PoolMeta
    __name__ = 'party.relation.all'

    portfolio = fields.Function(
        fields.Many2One('distribution.network', 'Portfolio'),
        'get_portfolio', searcher='search_portfolio')

    @fields.depends('from_')
    def on_change_with_portfolio(self, name=None):
        return self.from_.portfolio.id if self.from_ and \
            self.from_.portfolio else None

    @classmethod
    def get_portfolio(cls, instances, name):
        res = {}
        cursor = Transaction().connection.cursor()
        party = Pool().get('party.party').__table__()
        relation = cls.__table__()

        cursor.execute(*
            relation.join(party, 'LEFT OUTER',
                condition=(relation.from_ == party.id)).select(
                relation.id, party.portfolio,
                where=(relation.id.in_([x.id for x in instances]))))
        for relation_id, value in cursor.fetchall():
            res[relation_id] = value
        return res

    @classmethod
    def search_portfolio(cls, name, clause):
        return [('from_.portfolio',) + tuple(clause[1:])]

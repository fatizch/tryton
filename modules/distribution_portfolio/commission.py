# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

from trytond.modules.coog_core import fields

__all__ = [
    'Commission',
    'AggregatedCommission',
    ]


class Commission:
    __metaclass__ = PoolMeta
    __name__ = 'commission'

    portfolio = fields.Function(
        fields.Many2One('distribution.network', 'Portfolio'),
        'on_change_with_portfolio', searcher='search_portfolio')

    @fields.depends('commissioned_subscriber')
    def on_change_with_portfolio(self, name=None):
        return self.commissioned_subscriber.portfolio.id \
            if self.commissioned_subscriber and \
            self.commissioned_subscriber.portfolio else None

    @classmethod
    def search_portfolio(cls, name, clause):
        return ['OR',
            [('commissioned_option.parent_contract.subscriber.portfolio',) +
            tuple(clause[1:])],
            [('origin.invoice.party.portfolio',) +
            tuple(clause[1:]) + ('account.invoice.line',)],
            ]


class AggregatedCommission:
    __metaclass__ = PoolMeta
    __name__ = 'commission.aggregated'

    portfolio = fields.Function(
        fields.Many2One('distribution.network', 'Portfolio'),
        'on_change_with_portfolio', searcher='search_portfolio')

    @fields.depends('subscriber')
    def on_change_with_portfolio(self, name=None):
        return self.subscriber.portfolio.id \
            if self.subscriber and self.subscriber.portfolio else None

    @classmethod
    def search_portfolio(cls, name, clause):
        return ['OR',
            [('commissioned_option.parent_contract.subscriber.portfolio',) +
            tuple(clause[1:])],
            [('invoice.party.portfolio',) +
            tuple(clause[1:])],
            ]

# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict
from sql.aggregate import Count

from trytond.cache import Cache
from trytond.pool import PoolMeta
from trytond.pyson import Eval, Bool
from trytond.pool import Pool
from trytond.transaction import Transaction

from trytond.modules.coog_core import fields
__all__ = [
    'DistributionNetwork',
    ]


class DistributionNetwork:
    __metaclass__ = PoolMeta
    __name__ = 'distribution.network'

    portfolio_size = fields.Function(
        fields.Integer('Portfolio Size'),
        'get_portfolio_size')
    is_portfolio = fields.Boolean('Client Portfolio',
        states={'readonly': Bool(Eval('portfolio_size', False))},
        depends=['portfolio_size'],
        help='If checked, parties will be defined within this distribution'
        ' network and can only be accessed by it or its children distribution'
        ' network.')
    portfolio = fields.Function(
        fields.Many2One('distribution.network', 'Portfolio'),
        'get_portfolio')
    visible_portfolios = fields.Function(
        fields.Many2Many('distribution.network', None, None,
            'Visible Portfolios'),
        'get_visible_portfolios', searcher='search_visible_portfolios')
    _get_all_portfolios_cache = Cache('get_all_portfolios')

    @classmethod
    def create(cls, vlist):
        res = super(DistributionNetwork, cls).create(vlist)
        cls._get_all_portfolios_cache.clear()
        return res

    @classmethod
    def delete(cls, ids):
        res = super(DistributionNetwork, cls).delete(ids)
        cls._get_all_portfolios_cache.clear()
        return res

    @classmethod
    def write(cls, *args):
        res = super(DistributionNetwork, cls).write(*args)
        cls._get_all_portfolios_cache.clear()
        return res

    def get_visible_portfolios(self, name):
        return [x.id for x in self.search([
                    ['OR',
                        [('left', '>=', self.left),
                            ('right', '<=', self.right)],
                        [('left', '<', self.left),
                            ('right', '>', self.right)]],
                    [('is_portfolio', '=', True)]])]

    @classmethod
    def get_portfolio_size(cls, instances, name):
        pool = Pool()
        result = defaultdict(int)
        cursor = Transaction().connection.cursor()
        party = pool.get('party.party').__table__()
        cursor.execute(
            *party.select(party.portfolio, Count(party.id),
                where=(party.portfolio.in_([x.id for x in instances])),
                group_by=[party.portfolio]))
        for key, value in cursor.fetchall():
            result[key] = value
        return result

    def get_portfolio(self, name):
        if self.is_portfolio:
            return self.id
        if self.parent:
            portfolio = self.parent.portfolio
            return portfolio.id if portfolio else None

    @fields.depends('parent', 'is_portfolio')
    def on_change_parent(self):
        if self.parent:
            self.is_portfolio = not self.parent.portfolio
        else:
            self.is_portfolio = True

    @classmethod
    def search_visible_portfolios(cls, name, clause):
        if clause[1] == 'in':
            networks = cls.browse(clause[2])
            clause = [[('is_portfolio', '=', True)], ['OR']]
            for network in networks:
                clause[1].append([('left', '<=', network.left),
                        ('right', '=>', network.right)],
                    [('left', '>', network.left),
                        ('right', '<', network.right)])
            return clause
        else:
            raise NotImplementedError

    @classmethod
    def get_all_portfolios(cls):
        res = cls._get_all_portfolios_cache.get('all_portfolios', None)
        if res is None:
            res = [x.id for x in cls.search([('is_portfolio', '=', True)])]
            cls._get_all_portfolios_cache.set('all_portfolios', res)
        return res

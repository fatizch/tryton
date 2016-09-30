# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction

from trytond.modules.cog_utils import fields

__metaclass__ = PoolMeta
__all__ = [
    'Party',
    ]


class Party:
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

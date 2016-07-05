from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval
from trytond.transaction import Transaction

from trytond.modules.cog_utils import fields

__metaclass__ = PoolMeta
__all__ = [
    'Party',
    ]


class Party:
    __name__ = 'party.party'

    network = fields.One2Many('distribution.network', 'party', 'Network')
    portfolio = fields.Many2One('distribution.network', 'Portfolio',
        ondelete='RESTRICT', domain=[('is_portfolio', '=', True)], select=True)

    @classmethod
    def view_attributes(cls):
        return super(Party, cls).view_attributes() + [(
                '/form/notebook/page[@name="network"]',
                'states',
                {'invisible': ~Eval('network')}
                )]

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

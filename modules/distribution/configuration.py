from trytond.pool import PoolMeta
from trytond.modules.cog_utils import fields

__metaclass__ = PoolMeta
__all__ = [
    'Configuration',
    ]


class Configuration:
    __name__ = 'party.configuration'

    default_portfolio = fields.Property(
        fields.Many2One('distribution.network', 'Default Portfolio',
            domain=[('is_portfolio', '=', True)],
            help='This is the default portfolio if the user is not assigned to'
            ' any distribution network belonging to a portfolio.'))

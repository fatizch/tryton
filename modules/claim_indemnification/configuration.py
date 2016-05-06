from trytond.pool import PoolMeta
from trytond.modules.cog_utils import fields

__metaclass__ = PoolMeta
__all__ = [
    'Configuration'
    ]


class Configuration:
    'Claim Configuration'

    __name__ = 'claim.configuration'

    control_rule = fields.Many2One(
        'claim.indemnification.control.rule', 'Control Rule')

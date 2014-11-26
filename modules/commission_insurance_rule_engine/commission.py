from trytond.pool import PoolMeta

from trytond.modules.cog_utils import fields

__metaclass__ = PoolMeta
__all__ = [
    'Plan',
    ]


class Plan:
    __name__ = 'commission.plan'

    rule_engine_key = fields.Char('Rule Engine Key',
        help='key to retrieve the commission plan in rule engine algorithm')

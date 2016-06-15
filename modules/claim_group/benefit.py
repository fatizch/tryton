from trytond.pool import PoolMeta

from trytond.modules.cog_utils import fields

__all__ = [
    'Benefit',
    ]


class Benefit:
    __metaclass__ = PoolMeta
    __name__ = 'benefit'

    is_group = fields.Boolean('Group Benefit')

from trytond.pool import PoolMeta
from trytond.module.cog_utils import fields


__metaclass__ = PoolMeta
__all__ = [
    'Broker',
    ]


class Broker:

    __name__ = 'broker'

    orias = fields.Char('ORIAS Number')

from trytond.pool import PoolMeta

from trytond.modules.cog_utils import fields

__metaclass__ = PoolMeta
__all__ = [
    'Model',
    ]


class Model:
    __name__ = 'ir.model'

    printable = fields.Boolean('Printable')

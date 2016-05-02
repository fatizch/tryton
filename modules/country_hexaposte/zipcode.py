from trytond.pool import PoolMeta
from trytond.modules.cog_utils import fields


__metaclass__ = PoolMeta
__all__ = [
    'Zip',
    ]


class Zip:
    __name__ = 'country.zip'

    hexa_post_id = fields.Char('Hexa Post Id', select=True)

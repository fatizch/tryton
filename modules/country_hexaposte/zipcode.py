# -*- coding:utf-8 -*-
from trytond.pool import PoolMeta
from trytond.modules.cog_utils import fields


__metaclass__ = PoolMeta
__all__ = [
    'ZipCode',
    ]


class ZipCode:
    __name__ = 'country.zipcode'

    hexa_post_id = fields.Char('Hexa Post Id', select=True)

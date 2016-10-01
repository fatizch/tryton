# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.modules.coog_core import fields


__metaclass__ = PoolMeta
__all__ = [
    'Zip',
    ]


class Zip:
    __name__ = 'country.zip'

    hexa_post_id = fields.Char('Hexa Post Id', select=True)

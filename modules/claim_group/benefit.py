# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

from trytond.modules.cog_utils import fields

__all__ = [
    'Benefit',
    ]


class Benefit:
    __metaclass__ = PoolMeta
    __name__ = 'benefit'

    is_group = fields.Boolean('Group Benefit')

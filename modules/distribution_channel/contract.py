# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

from trytond.modules.coog_core import fields

__all__ = [
    'Contract',

    ]


class Contract(metaclass=PoolMeta):
    __name__ = 'contract'

    dist_channel = fields.Many2One('distribution.channel',
        'Channel', ondelete='RESTRICT')

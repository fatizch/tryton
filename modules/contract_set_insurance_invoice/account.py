# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

from trytond.modules.cog_utils import fields

__metaclass__ = PoolMeta
__all__ = [
    'Fee',
    ]


class Fee:
    __name__ = 'account.fee'

    one_per_set = fields.Boolean('One Per Set')

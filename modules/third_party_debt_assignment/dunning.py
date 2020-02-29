# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

from trytond.modules.coog_core import fields

__all__ = [
    'Level',
    ]


class Level(metaclass=PoolMeta):
    __name__ = 'account.dunning.level'

    ask_for_third_party_take_care = fields.Boolean(
        'Ask for third party take care', help='If set, the contract that has '
        'an account dunning with this level, a debt assignment request '
        'will be created for')

# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

from trytond.modules.coog_core import fields

__all__ = [
    'OptionDescription',
    ]


class OptionDescription(metaclass=PoolMeta):
    __name__ = 'offered.option.description'

    allow_third_party_assignment = fields.Boolean(
        'Allow third party assignment', help='If set, The insurer party will be'
        ' the third party in the debt assignment request of the subscriber')

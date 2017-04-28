# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

from trytond.modules.coog_core import fields


__all__ = [
    'ClaimConfiguration',
    ]


class ClaimConfiguration:
    __metaclass__ = PoolMeta
    __name__ = 'claim.configuration'

    eckert_law_target_delay = fields.Integer('Eckert Law Target Delay',
        help='Number of days which is allowed to pay Eckert Law capitals')
    eckert_law_default_delay = fields.Integer('Eckert Law Delay',
        help='The number of days that will be set by default between the '
        'current date and the target indemnification date for Eckert capital '
        'indemnifications')

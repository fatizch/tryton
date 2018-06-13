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

    prest_ij_sequence = fields.Many2One('ir.sequence', 'IJ Flow Sequence',
        required=True, ondelete='RESTRICT')
    prest_ij_period_sequence = fields.Many2One('ir.sequence',
        'IJ Period Sequence', required=True, ondelete='RESTRICT')

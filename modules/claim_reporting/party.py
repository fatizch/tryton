# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

from trytond.modules.coog_core import fields

__all__ = [
    'Insurer',
    ]


class Insurer:
    __name__ = 'insurer'
    __metaclass__ = PoolMeta

    claim_stock_reports = fields.Many2Many('insurer-report.template', 'insurer',
        'report_template', 'Claim Stock Reports',
        domain=[('kind', '=', 'claim_insurer_report')])

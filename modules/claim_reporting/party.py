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

    # Use function field for Export/import purpose as data are already included
    # in stock_reports fields
    claim_stock_reports = fields.Function(
        fields.Many2Many('insurer-report.template', None,
        None, 'Claim Stock Reports'),
        'get_claim_stock_reports')

    def get_claim_stock_reports(self, name):
        return [x for x in self.stock_reports
            if x.kind == 'claim_insurer_report']

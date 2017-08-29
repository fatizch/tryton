# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

from trytond.modules.coog_core import fields, model


__all__ = [
    'InsurerReportTemplate',
    'Insurer',
    ]


class InsurerReportTemplate(model.CoogSQL):
    'Insurer Report Template'
    __name__ = 'insurer-report.template'

    insurer = fields.Many2One('insurer', 'Insurer',
        select=True, ondelete='CASCADE')
    report_template = fields.Many2One('report.template', 'Report Template',
        select=True, ondelete='CASCADE')


class Insurer:
    __name__ = 'insurer'
    __metaclass__ = PoolMeta

    stock_reports = fields.Many2Many('insurer-report.template', 'insurer',
        'report_template', 'Stock Reports', domain=[
            ('kind', 'like', 'insurer_report_%')])

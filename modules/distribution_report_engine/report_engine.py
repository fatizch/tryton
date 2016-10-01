# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

from trytond.modules.coog_core import fields, model


__all__ = [
    'ReportTemplate',
    'ReportComProductRelation',
    ]


class ReportComProductRelation(model.CoogSQL):
    'Report template to Commercial Product relation'
    __metaclass__ = PoolMeta
    __name__ = 'report.template-distribution.commercial_product'

    report_template = fields.Many2One('report.template', 'Document',
        ondelete='RESTRICT')
    com_product = fields.Many2One('distribution.commercial_product',
        'Commercial Product', ondelete='CASCADE')


class ReportTemplate:
    __name__ = 'report.template'
    __metaclass__ = PoolMeta

    com_products = fields.Many2Many(
        'report.template-distribution.commercial_product',
        'report_template', 'com_product', 'Commercial Products')

    @classmethod
    def _export_skips(cls):
        return super(ReportTemplate, cls)._export_skips() | {'com_products'}

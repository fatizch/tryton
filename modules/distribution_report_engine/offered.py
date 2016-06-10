from trytond.modules.cog_utils import fields
from trytond.pool import PoolMeta

__all__ = [
    'CommercialProduct',
    ]


class CommercialProduct:

    __metaclass__ = PoolMeta
    __name__ = 'distribution.commercial_product'

    report_templates = fields.Many2Many(
        'report.template-distribution.commercial_product',
        'com_product', 'report_template', 'Report Templates')
    report_style_template = fields.Binary('Report Style')

    def get_report_style_content(self, at_date, template, contract=None):
        if template.template_extension == 'odt':
            return self.report_style_template

    @classmethod
    def _export_light(cls):
        return super(CommercialProduct, cls)._export_light() | {
            'report_templates'}

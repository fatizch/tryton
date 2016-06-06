from trytond import backend
from trytond.pool import PoolMeta
from trytond.transaction import Transaction

from trytond.modules.cog_utils import fields, model


__metaclass__ = PoolMeta
__all__ = [
    'ReportProductRelation',
    'ReportTemplate',
    ]


class ReportTemplate:
    __name__ = 'report.template'

    products = fields.Many2Many('report.template-offered.product',
        'report_template', 'product', 'Products')

    @classmethod
    def _export_skips(cls):
        return super(ReportTemplate, cls)._export_skips() | {'products'}


class ReportProductRelation(model.CoopSQL):
    'Report template to Product relation'

    __name__ = 'report.template-offered.product'

    report_template = fields.Many2One('report.template', 'Document',
        ondelete='RESTRICT')
    product = fields.Many2One('offered.product', 'Product', ondelete='CASCADE')

    @classmethod
    def __register__(cls, module_name):
        # Migration from 1.3: rename 'document_template' => 'report_template'
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().connection.cursor()
        if TableHandler.table_exist(
                'document_template-offered_product'):
            TableHandler.table_rename(
                'document_template-offered_product',
                'report_template-offered_product')
            cursor.execute('ALTER TABLE "report_template-offered_product" '
                "RENAME COLUMN document_template TO report_template")
        super(ReportProductRelation, cls).__register__(module_name)

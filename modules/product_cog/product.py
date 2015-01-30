from trytond.pool import PoolMeta, Pool

from trytond.modules.cog_utils import export

__metaclass__ = PoolMeta
__all__ = [
    'Template',
    'Product',
    'Uom',
    ]


class Template(export.ExportImportMixin):
    __name__ = 'product.template'
    _func_key = 'name'

    @classmethod
    def _export_light(cls):
        return (super(Template, cls)._export_light() |
            set(['default_uom', 'account_expense', 'account_revenue']))

    @classmethod
    def _export_skips(cls):
        return (super(Template, cls)._export_skips() | set(['products']))

    @staticmethod
    def default_type():
        return 'service'

    @classmethod
    def default_default_uom(cls):
        UOM = Pool().get('product.uom')
        uom, = UOM.search([('symbol', '=', 'u')])
        return uom.id


class Product(export.ExportImportMixin):
    __name__ = 'product.product'
    _func_key = 'code'


class Uom(export.ExportImportMixin):
    __name__ = 'product.uom'
    _func_key = 'name'

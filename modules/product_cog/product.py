# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool

from trytond.modules.coog_core import export, fields

__metaclass__ = PoolMeta
__all__ = [
    'Template',
    'Product',
    'Uom',
    'Category',
    ]


class Template(export.ExportImportMixin):
    __name__ = 'product.template'
    _func_key = 'name'

    @classmethod
    def __setup__(cls):
        super(Template, cls).__setup__()
        cls.account_expense.domain = cls.account_expense.domain[1:] + [[
                'OR',
                [('kind', '=', 'expense')],
                [('kind', '=', 'other')],
                ]]
        cls.account_revenue.domain = cls.account_revenue.domain[1:] + [[
                'OR',
                [('kind', '=', 'revenue')],
                [('kind', '=', 'other')],
                ]]

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


class Category(export.ExportImportMixin):
    __name__ = 'product.category'
    _func_key = 'code'

    code = fields.Char('Code', required=True)

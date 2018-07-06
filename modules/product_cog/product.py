# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Null
from trytond.pool import PoolMeta, Pool
from trytond.model import Unique
from trytond.transaction import Transaction

from trytond.modules.coog_core import export, fields, coog_string

__all__ = [
    'Template',
    'TemplateAccount',
    'Product',
    'Uom',
    'Category',
    ]


class Template(export.ExportImportMixin):
    __name__ = 'product.template'
    _func_key = 'name'

    taxes_included = fields.Boolean('Taxes Included')

    @classmethod
    def __register__(cls, module_name):
        super(Template, cls).__register__(module_name)
        table = cls.__table__()
        # Migration from 1.14
        cursor = Transaction().connection.cursor()
        cursor.execute(*table.update(
                columns=[table.name],
                values=[table.id],
                where=table.name == Null))

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
        cls.name.required = True
        t = cls.__table__()
        cls._sql_constraints += [
            ('name_uniq', Unique(t, t.name), 'The name must be unique.'),
            ]

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


class TemplateAccount:
    __metaclass__ = PoolMeta
    __name__ = 'product.template.account'

    @classmethod
    def __setup__(cls):
        super(TemplateAccount, cls).__setup__()
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


class Product(export.ExportImportMixin):
    __name__ = 'product.product'
    _func_key = 'code'

    @fields.depends('name', 'code')
    def on_change_with_code(self):
        if self.code:
            return self.code
        elif self.name:
            return coog_string.slugify(self.name)

    @classmethod
    def __register__(cls, module_name):
        table = cls.__table__()
        # Migration from 1.14
        cursor = Transaction().connection.cursor()
        cursor.execute(*table.update(
                columns=[table.code],
                values=[table.id],
                where=(table.code == Null) | (table.code == '')))
        super(Product, cls).__register__(module_name)

    @classmethod
    def __setup__(cls):
        super(Product, cls).__setup__()
        cls.code.required = True
        t = cls.__table__()
        cls._sql_constraints += [
            ('code_uniq', Unique(t, t.code), 'The code must be unique.'),
            ]

    def get_rec_name(self, name):
        return self.name


class Uom(export.ExportImportMixin):
    __name__ = 'product.uom'
    _func_key = 'name'


class Category(export.ExportImportMixin):
    __name__ = 'product.category'
    _func_key = 'code'

    code = fields.Char('Code', required=True)

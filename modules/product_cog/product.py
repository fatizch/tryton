# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal

from sql import Null
from trytond.pool import Pool
from trytond.model import Unique
from trytond.transaction import Transaction

from trytond.modules.coog_core import export, fields, coog_string

__all__ = [
    'Template',
    'TemplateAccount',
    'Product',
    'Uom',
    'Category',
    'ProductCostPrice',
    'ProductListPrice',
    'ProductCostPriceMethod',
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


class TemplateAccount(export.ExportImportMixin):
    __name__ = 'product.template.account'
    _func_key = 'func_key'

    func_key = fields.Function(fields.Char('Func Key'),
        'getter_func_key', searcher='searcher_func_key')

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

    def getter_func_key(self, name):
        return '|'.join([
                self.template.name,
                self.account_expense.code if self.account_expense else '',
                self.account_revenue.code if self.account_revenue else '',
                ])

    @classmethod
    def searcher_func_key(cls, name, clause):
        assert clause[1] == '='
        template, account_expense, account_revenue = clause[2].split('|')
        account_expense = int(account_expense) if account_expense else None
        account_revenue = int(account_revenue) if account_revenue else None

        return [('template.name', '=', int(template)),
            ('account_expense.code', '=', account_expense),
            ('account_revenue.code', '=', account_revenue),
            ]


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


class ProductCostPrice(export.ExportImportMixin):
    __name__ = 'product.cost_price'
    _func_key = 'func_key'

    func_key = fields.Function(fields.Char('Func Key'),
        'getter_func_key', searcher='searcher_func_key')

    def getter_func_key(self, name):
        return '|'.join([
                self.product.code,
                str(self.cost_price),
                ])

    @classmethod
    def searcher_func_key(cls, name, clause):
        assert clause[1] == '='
        product_code, cost_price = clause[2].split('|')
        return [('product.code', '=', product_code),
            ('cost_price', '=', Decimal(cost_price))]


class ProductListPrice(export.ExportImportMixin):
    __name__ = 'product.list_price'
    _func_key = 'func_key'

    func_key = fields.Function(fields.Char('Func Key'),
        'getter_func_key', searcher='searcher_func_key')

    def getter_func_key(self, name):
        return '|'.join([
                self.template.name,
                str(self.list_price),
                ])

    @classmethod
    def searcher_func_key(cls, name, clause):
        assert clause[1] == '='
        template_name, list_price = clause[2].split('|')
        return [('template.name', '=', template_name),
            ('list_price', '=', Decimal(list_price))]


class ProductCostPriceMethod(export.ExportImportMixin):
    __name__ = 'product.cost_price_method'
    _func_key = 'func_key'

    func_key = fields.Function(fields.Char('Func Key'),
        'getter_func_key', searcher='searcher_func_key')

    def getter_func_key(self, name):
        return '|'.join([
                self.template.name,
                str(self.cost_price_method),
                ])

    @classmethod
    def searcher_func_key(cls, name, clause):
        assert clause[1] == '='
        template, cost_price_method = clause[2].split('|')
        return [('template.name', '=', template),
            ('cost_price_method', '=', cost_price_method)]

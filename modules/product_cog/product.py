# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
from decimal import Decimal

from sql import Null, Table
from trytond.pool import Pool, PoolMeta
from trytond.model import Unique
from trytond.transaction import Transaction
from trytond.pyson import Eval
from trytond import backend

from trytond.modules.coog_core import export, fields, coog_string

__all__ = [
    'Template',
    'Product',
    'Uom',
    'Category',
    'ProductCostPrice',
    'ProductListPrice',
    'ProductCostPriceMethod',
    'CategoryAccount',
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
        cls.name.required = True
        t = cls.__table__()
        cls._sql_constraints += [
            ('name_uniq', Unique(t, t.name), 'The name must be unique.'),
            ]

    @classmethod
    def _export_light(cls):
        return (super(Template, cls)._export_light() |
            set(['default_uom']))

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

    @classmethod
    def __setup__(cls):
        super(Category, cls).__setup__()
        account_revenue_original_domain = cls.account_revenue.domain
        assert account_revenue_original_domain == [
                ('kind', '=', 'revenue'),
                ('company', '=', Eval('context', {}).get('company', -1)),
                ], account_revenue_original_domain
        cls.account_revenue.domain = [['OR', ('kind', '=', 'other'),
            account_revenue_original_domain[0]],
            account_revenue_original_domain[1]]
        account_expense_original_domain = cls.account_expense.domain
        assert account_expense_original_domain == [
                ('kind', '=', 'expense'),
                ('company', '=', Eval('context', {}).get('company', -1)),
                ], account_expense_original_domain
        cls.account_expense.domain = [['OR', ('kind', '=', 'other'),
            account_expense_original_domain[0]],
            account_expense_original_domain[1]]

    @classmethod
    def __register__(cls, module_name):
        super(Category, cls).__register__(module_name)
        # Migration from 4.8 : create accounting_category for Product Templates
        Template = Pool().get('product.template')
        template = Template.__table__()
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().connection.cursor()
        product_category = Table('product_category')
        product_template_account = Table('product_template_account')
        product_category_account = Table('product_category_account')
        category_customer_tax = Table('product_category_customer_taxes_rel')
        category_supplier_tax = Table('product_category_supplier_taxes_rel')
        template_customer_tax = Table('product_customer_taxes_rel')
        template_supplier_tax = Table('product_supplier_taxes_rel')

        exist = TableHandler.table_exist('product_template_account')
        if not exist:
            return

        cursor.execute(*template.select(template.id,
                where=(template.account_category == Null)))
        to_migrate = [x[0] for x in cursor.fetchall()]
        if not to_migrate:
            return

        cursor.execute(*product_template_account.join(template, condition=(
                    (product_template_account.template == template.id) & (
                        template.id.in_(to_migrate)))
                ).select(
                    product_template_account.company,
                    template.name,
                    product_template_account.account_expense,
                    product_template_account.account_revenue))
        res = list(cursor.fetchall())
        now = datetime.datetime.now()
        product_category_insert_columns = [
            product_category.name,
            product_category.code,
            product_category.accounting,
            product_category.create_uid,
            product_category.create_date,
        ]
        product_category_account_insert_columns = [
            product_category_account.company,
            product_category_account.category,
            product_category_account.account_expense,
            product_category_account.account_revenue,
            product_category_account.create_uid,
            product_category_account.create_date,
            ]
        for company, name, account_expense, account_revenue in res:
            code = coog_string.slugify(name)
            product_category_insert_values = [
                name, code, True, 0, now]
            cursor.execute(*product_category.insert(
                    product_category_insert_columns,
                    [product_category_insert_values],
                    [product_category.id]))
            category_id, = cursor.fetchone()

            product_category_account_insert_values = [
                company, category_id, account_expense, account_revenue,
                0, now]
            cursor.execute(*product_category_account.insert(
                    product_category_account_insert_columns,
                    [product_category_account_insert_values]))
            cursor.execute(*template.update(
                    columns=[template.account_category],
                    values=[category_id],
                    where=(template.name == name)))
        # Link taxes to category

        for old, new in [(template_customer_tax, category_customer_tax),
                (template_supplier_tax, category_supplier_tax)]:
            cursor.execute(*old.join(template,
                    condition=(old.product == template.id)
                    ).select(template.account_category, old.tax))
            for category, tax in cursor.fetchall():
                values = [category, tax, 0, now]
                cursor.execute(*new.insert([new.category, new.tax,
                            new.create_uid, new.create_date], [values]))

        TableHandler.drop_table('product.template.account',
            'product_template_account')
        TableHandler.drop_table('product.template-customer-account.tax',
            'product_customer_taxes_rel')
        TableHandler.drop_table('product.template-supplier-account.tax',
            'product_supplier_taxes_rel')
        # End of Migration from 4.8

    @classmethod
    def _export_light(cls):
        return super(Category, cls)._export_light() | {
            'company', 'parent', 'accounts', 'customer_taxes', 'childs'
            }


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


class CategoryAccount(export.ExportImportMixin, metaclass=PoolMeta):
    __name__ = 'product.category.account'
    _func_key = 'func_key'

    func_key = fields.Function(fields.Char('Func Key'),
        'getter_func_key', searcher='searcher_func_key')

    @classmethod
    def __setup__(cls):
        super(CategoryAccount, cls).__setup__()
        account_revenue_original_domain = cls.account_revenue.domain
        assert account_revenue_original_domain == [
                ('kind', '=', 'revenue'),
                ('company', '=', Eval('company', -1)),
                ], account_revenue_original_domain
        cls.account_revenue.domain = [['OR', ('kind', '=', 'other'),
            account_revenue_original_domain[0]],
            account_revenue_original_domain[1]]
        account_expense_original_domain = cls.account_expense.domain
        assert account_expense_original_domain == [
                ('kind', '=', 'expense'),
                ('company', '=', Eval('company', -1)),
                ], account_expense_original_domain
        cls.account_expense.domain = [['OR', ('kind', '=', 'other'),
            account_expense_original_domain[0]],
            account_expense_original_domain[1]]

    def getter_func_key(self, name):
        expense_code = self.account_expense.code if self.account_expense \
            else ''
        revenue_code = self.account_revenue.code if self.account_revenue \
            else ''
        return '%s|%s' % (expense_code, revenue_code)

    @classmethod
    def searcher_func_key(cls, name, clause):
        assert clause[1] == '='
        expense_code, revenue_code = clause[2].split('|')
        return [('account_expense.code', '=', expense_code),
            ('account_revenue.code', '=', revenue_code)]

    @classmethod
    def _export_light(cls):
        return (super(CategoryAccount, cls)._export_light() |
            set(['account_expense', 'account_revenue', 'category', 'company']
                ))

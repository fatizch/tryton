# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Literal, Window
from sql.aggregate import Min
from sql.conditionals import Coalesce
from sql.functions import RowNumber

from trytond.pool import Pool
from trytond.model import Unique
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond import backend

from trytond.modules.coog_core import model, utils, fields
from trytond.modules.coog_core import coog_string
from trytond.modules.currency_cog import ModelCurrency

from .extra_data import with_extra_data_def, with_extra_data

__all__ = [
    'Product',
    'OptionDescription',
    'OptionDescriptionExtraDataRelation',
    'ProductOptionDescriptionRelation',
    'ProductExtraDataRelation',
    'OptionDescriptionRequired',
    'OptionDescriptionExcluded',
    ]

SUBSCRIBER_KIND = [
    ('all', 'All'),
    ('person', 'Person'),
    ('company', 'Company'),
    ]

SUBSCRIPTION_BEHAVIOUR = [
    ('mandatory', 'Mandatory'),
    ('defaulted', 'Defaulted'),
    ('optional', 'Optional'),
    ]


class Product(model.CoogSQL, model.CoogView,
        with_extra_data_def('offered.product-extra_data', 'product',
            'contract'),
        with_extra_data(['product'], field_string='Offered Kind'),
        model.TaggedMixin):
    'Product'

    __name__ = 'offered.product'
    _func_key = 'code'

    code = fields.Char('Code', required=True)
    name = fields.Char('Name', required=True, translate=True)
    company = fields.Many2One('company.company', 'Company', required=True,
        ondelete='RESTRICT')
    start_date = fields.Date('Start Date', required=True)
    end_date = fields.Date('End Date')
    description = fields.Text('Description', translate=True)
    coverages = fields.Many2Many('offered.product-option.description',
        'product', 'coverage', 'Option Descriptions', domain=[
            ('currency', '=', Eval('currency')),
            ('company', '=', Eval('company')),
            ], depends=['currency', 'company'],
        order=[('coverage.sequence', 'ASC NULLS LAST')])
    packages = fields.Many2Many('offered.product-package', 'product',
        'package', 'Packages', domain=[('options', 'in', Eval('coverages'))],
        depends=['coverages'])
    currency = fields.Many2One('currency.currency', 'Currency', required=True,
        ondelete='RESTRICT')
    currency_digits = fields.Function(
        fields.Integer('Currency Digits'),
        'on_change_with_currency_digits')
    currency_symbol = fields.Function(
        fields.Char('Currency Symbol'),
        'on_change_with_currency_symbol')
    contract_generator = fields.Many2One('ir.sequence',
        'Contract Number Generator', context={'code': 'offered.product'},
        ondelete='RESTRICT', required=True,
        domain=[('code', '=', 'contract')])
    subscriber_kind = fields.Selection(SUBSCRIBER_KIND, 'Subscriber Kind')
    report_templates = fields.Many2Many('report.template-offered.product',
        'product', 'report_template', 'Report Templates')
    report_style_template = fields.Binary('Report Style')
    data_shelf_life = fields.Integer('Data Shelf Life',
        domain=['OR',
            [('data_shelf_life', '=', None)],
            [('data_shelf_life', '>=', 0)]],
        help='The number of years contract\'s data related to this product '
        'can be kept after the contract\'s termination.')
    icon = fields.Many2One('ir.ui.icon', 'Icon', ondelete='RESTRICT',
        help='This icon will be used to quickly identify the product')
    icon_name = fields.Function(
        fields.Char('Icon Name'),
        'getter_icon_name')

    @classmethod
    def __setup__(cls):
        super(Product, cls).__setup__()
        cls._export_binary_fields.add('report_style_template')
        t = cls.__table__()
        cls._sql_constraints += [
            ('code_uniq', Unique(t, t.code), 'The code must be unique!'),
            ]
        cls._error_messages.update({
                'missing_contract_extra_data': 'The following contract extra'
                'data should be set on the product: %s',
                })

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        table = TableHandler(cls, module_name)

        super(Product, cls).__register__(module_name)

        # Migration from 1.6 Drop Offered inheritance
        if table.column_exist('template'):
            table.drop_column('template')
            table.drop_column('template_behaviour')

    @classmethod
    def is_master_object(cls):
        return True

    @classmethod
    def _export_light(cls):
        return super(Product, cls)._export_light() | {'contract_generator',
            'company', 'currency', 'report_templates'}

    @classmethod
    def validate(cls, instances):
        super(Product, cls).validate(instances)
        cls.validate_contract_extra_data(instances)

    @classmethod
    def validate_contract_extra_data(cls, instances):
        for instance in instances:
            from_option = set(extra_data for coverage in instance.coverages
                for extra_data in coverage.extra_data_def
                if extra_data.kind == 'contract')
            remaining = from_option - set(instance.extra_data_def)
            if remaining:
                instance.raise_user_error('missing_contract_extra_data',
                    (', '.join((extra_data.string
                                for extra_data in remaining))))

    def getter_icon_name(self, name):
        if self.icon:
            return self.icon.name
        return ''

    @classmethod
    def search_rec_name(cls, name, clause):
        return ['OR',
            [(u'name',) + tuple(clause[1:])],
            [(u'code',) + tuple(clause[1:])]
            ]

    @classmethod
    def default_currency(cls):
        return ModelCurrency.default_currency()

    @staticmethod
    def default_subscriber_kind():
        return 'all'

    @staticmethod
    def default_start_date():
        return Transaction().context.get('start_date', None) or utils.today()

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company', None)

    def get_valid_coverages(self):
        for coverage in self.coverages:
            if coverage.is_valid():
                yield coverage

    def init_dict_for_rule_engine(self, args):
        if 'product' not in args:
            args['product'] = self

    def new_contract_number(self):
        return (self.contract_generator.get_id(self.contract_generator.id)
            if self.contract_generator else '')

    def get_currency(self):
        return self.currency

    def check_subscriber_kind(self, args):
        # We define a match_table which will tell what data to look for
        # depending on the subscriber_eligibility attribute value.
        match_table = {
            'all': 'subscriber',
            'person': 'subscriber_person',
            'company': 'subscriber_company'}

        # if it does not match, refusal
        if not match_table[self.subscriber_kind] in args:
            return (False, ['Subscriber must be a %s'
                    % dict(SUBSCRIBER_KIND)[self.subscriber_kind]])
        return True, []

    def get_publishing_values(self):
        result = super(Product, self).get_publishing_values()
        result['name'] = self.name
        result['code'] = self.code
        return result

    def get_report_style_content(self, at_date, template, contract=None):
        if template.input_kind == 'libre_office_odt':
            if self.report_style_template is not None:
                return self.report_style_template
            configuration = Pool().get('offered.configuration').get_singleton()
            if configuration is not None:
                if configuration.use_default_style:
                    return configuration.style_template

    @fields.depends('currency')
    def on_change_with_currency_digits(self, name=None):
        return self.currency.digits if self.currency else 2

    @fields.depends('currency')
    def on_change_with_currency_symbol(self, name=None):
        return self.currency.symbol if self.currency else ''


class OptionDescription(model.CoogSQL, model.CoogView,
        with_extra_data_def('offered.option.description-extra_data',
            'coverage', 'option'),
        with_extra_data(['product'], field_string='Offered Kind'),
        model.TaggedMixin):
    'OptionDescription'

    __name__ = 'offered.option.description'
    _func_key = 'code'

    code = fields.Char('Code', required=True)
    name = fields.Char('Name', required=True, translate=True)
    company = fields.Many2One('company.company', 'Company', required=True,
        ondelete='RESTRICT')
    start_date = fields.Date('Start Date', required=True)
    end_date = fields.Date('End Date')
    description = fields.Text('Description', translate=True)
    currency = fields.Many2One('currency.currency', 'Currency', required=True,
        ondelete='RESTRICT')
    currency_digits = fields.Function(
        fields.Integer('Currency Digits'),
        'on_change_with_currency_digits')
    currency_symbol = fields.Function(
        fields.Char('Currency Symbol'),
        'on_change_with_currency_symbol')
    subscription_behaviour = fields.Selection(SUBSCRIPTION_BEHAVIOUR,
        'Subscription Behaviour', sort=False)
    options_required = fields.Many2Many('offered.option.description.required',
        'from_option_desc', 'to_option_desc', 'Options Required', domain=[
            ('id', '!=', Eval('id')),
            ('id', 'not in', Eval('options_excluded')),
            ], depends=['id', 'options_excluded'])
    options_excluded = fields.Many2Many('offered.option.description.excluded',
        'from_option_desc', 'to_option_desc', 'Options Excluded', domain=[
            ('id', '!=', Eval('id')),
            ('id', 'not in', Eval('options_required')),
            ], depends=['id', 'options_required'])
    products = fields.Many2Many('offered.product-option.description',
        'coverage', 'product', 'Products', domain=[
            ('currency', '=', Eval('currency')),
            ('company', '=', Eval('company')),
            ], depends=['currency', 'company'])
    sequence = fields.Integer('Sequence', help='Used to order the coverages '
        'accross the application')
    products_name = fields.Function(
        fields.Char('Products'),
        'on_change_with_products_name', searcher='search_products')
    is_service = fields.Function(
        fields.Boolean('Is a Service'),
        'on_change_with_is_service')
    ending_rule = fields.One2Many('offered.option.description.ending_rule',
        'coverage', 'Ending Rule', size=1, delete_missing=True)

    @classmethod
    def __setup__(cls):
        super(OptionDescription, cls).__setup__()
        t = cls.__table__()
        cls._order = [('sequence', 'ASC NULLS LAST')]
        cls._sql_constraints += [
            ('code_uniq', Unique(t, t.code), 'The code must be unique!'),
            ]

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        handler = TableHandler(cls, module_name)
        Relation = Pool().get('offered.product-option.description')

        # Migrate from 1.10 Use global ordering for coverages
        migrate_sequence = (not handler.column_exist('sequence') and
            TableHandler.table_exist(Relation._table))

        super(OptionDescription, cls).__register__(module_name)

        if migrate_sequence:
            cursor = Transaction().connection.cursor()
            table = cls.__table__()
            old_table = Relation.__table__()
            window_coverage = Window([])
            sub_query = old_table.select(old_table.coverage,
                Min(Coalesce(old_table.order, Literal(0))).as_('sequence'),
                group_by=[old_table.coverage],
                order_by=[
                    Min(Coalesce(old_table.order, Literal(0)))])
            values = sub_query.select(
                sub_query.coverage,
                RowNumber(window=window_coverage).as_('number'))

            cursor.execute(*table.update(
                    columns=[table.sequence],
                    values=[values.number],
                    from_=[values],
                    where=values.coverage == table.id))

    @classmethod
    def is_master_object(cls):
        return True

    @classmethod
    def _export_light(cls):
        return super(OptionDescription, cls)._export_light() | {'company',
            'currency', 'tags'}

    @classmethod
    def _export_skips(cls):
        return (super(OptionDescription, cls)._export_skips() |
            set(['products']))

    @classmethod
    def copy(cls, options, default=None):
        default = {} if default is None else default.copy()
        default.setdefault('products', None)
        return super(OptionDescription, cls).copy(options, default=default)

    @classmethod
    def default_currency(cls):
        return ModelCurrency.default_currency()

    @staticmethod
    def default_subscription_behaviour():
        return 'mandatory'

    @staticmethod
    def default_is_service():
        return True

    @staticmethod
    def default_start_date():
        return Transaction().context.get('start_date', None) or utils.today()

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company', None)

    @classmethod
    def get_possible_coverages_clause(cls, instance, at_date):
        date_clause = [['OR',
                ('start_date', '=', None),
                ('start_date', '<=', at_date)],
            ['OR',
                ('end_date', '=', None),
                ('end_date', '>=', at_date)]]
        if instance and instance.__name__ == 'contract':
            return [('products', '=', instance.product.id)] + date_clause
        return date_clause

    def get_currency(self):
        return self.currency

    def get_publishing_values(self):
        result = super(OptionDescription, self).get_publishing_values()
        result['name'] = self.name
        result['code'] = self.code
        return result

    @classmethod
    def search_rec_name(cls, name, clause):
        return ['OR',
            [(u'name',) + tuple(clause[1:])],
            [(u'code',) + tuple(clause[1:])]
            ]

    @classmethod
    def search_products(cls, name, clause):
        return ['OR',
            ('products.code',) + tuple(clause[1:]),
            ('products.name',) + tuple(clause[1:])
            ]

    def is_valid(self):
        if self.template_behaviour == 'remove':
            return False
        return True

    def on_change_with_is_service(self, name=None):
        return True

    @fields.depends('products')
    def on_change_with_products_name(self, name=None):
        return ', '.join([x.rec_name for x in self.products])

    @fields.depends('currency')
    def on_change_with_currency_digits(self, name=None):
        return self.currency.digits if self.currency else 2

    @fields.depends('currency')
    def on_change_with_currency_symbol(self, name=None):
        return self.currency.symbol if self.currency else ''

    @fields.depends('code', 'name')
    def on_change_with_code(self):
        return self.code if self.code else coog_string.slugify(self.name)

    def init_dict_for_rule_engine(self, args):
        args['coverage'] = self

    def calculate_end_date(self, exec_context):
        if self.ending_rule:
            return self.ending_rule[0].calculate_rule(exec_context)


class OptionDescriptionExtraDataRelation(model.CoogSQL):
    'Relation between OptionDescription and Extra Data'

    __name__ = 'offered.option.description-extra_data'

    coverage = fields.Many2One('offered.option.description',
        'Option Description', ondelete='CASCADE')
    extra_data_def = fields.Many2One('extra_data', 'Extra Data',
        ondelete='RESTRICT')


class ProductOptionDescriptionRelation(model.CoogSQL, model.CoogView):
    'Product to Option Description Relation'

    __name__ = 'offered.product-option.description'

    product = fields.Many2One('offered.product', 'Product', ondelete='CASCADE',
        required=True, select=True)
    coverage = fields.Many2One('offered.option.description',
        'Option Description', ondelete='RESTRICT', required=True, select=True)

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        handler = TableHandler(cls, module_name)

        # Migrate from 1.10 Use global ordering for coverages
        migrate_sequence = handler.column_exist('order')

        super(ProductOptionDescriptionRelation, cls).__register__(module_name)

        if migrate_sequence:
            handler.drop_column('order')


class ProductExtraDataRelation(model.CoogSQL):
    'Relation between Product and Extra Data'

    __name__ = 'offered.product-extra_data'

    product = fields.Many2One('offered.product', 'Product', ondelete='CASCADE')
    extra_data_def = fields.Many2One('extra_data', 'Extra Data',
        ondelete='RESTRICT')


class OptionDescriptionRequired(model.CoogSQL):
    'Option Description Required'

    __name__ = 'offered.option.description.required'

    from_option_desc = fields.Many2One('offered.option.description',
        'From Option Description', ondelete='CASCADE')
    to_option_desc = fields.Many2One('offered.option.description',
        'To Option Description', ondelete='RESTRICT')


class OptionDescriptionExcluded(model.CoogSQL):
    'Option Description Excluded'

    __name__ = 'offered.option.description.excluded'

    from_option_desc = fields.Many2One('offered.option.description',
        'From Option Description', ondelete='CASCADE')
    to_option_desc = fields.Many2One('offered.option.description',
        'To Option Description', ondelete='RESTRICT')

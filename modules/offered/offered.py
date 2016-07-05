# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from trytond.model import Unique
from trytond.pyson import Eval, Bool
from trytond.transaction import Transaction
from trytond.rpc import RPC
from trytond import backend

from trytond.modules.cog_utils import model, utils, fields
from trytond.modules.cog_utils import coop_string
from trytond.modules.currency_cog import ModelCurrency

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


class Product(model.CoopSQL, model.CoopView, model.TaggedMixin):
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
    extra_data = fields.Dict('extra_data', 'Offered Kind',
        context={'extra_data_kind': 'product'},
        domain=[('kind', '=', 'product')])
    extra_data_string = extra_data.translated('extra_data')
    coverages = fields.Many2Many('offered.product-option.description',
        'product', 'coverage', 'Option Descriptions', domain=[
            ('currency', '=', Eval('currency')),
            ('company', '=', Eval('company')),
            ], depends=['currency', 'company'],
            order=[('order', 'ASC')],
            states={'invisible': Bool(Eval('change_coverages_order'))})
    change_coverages_order = fields.Function(
        fields.Boolean('Change Order'),
        'get_change_coverages_order', 'setter_void')
    ordered_coverages = fields.One2Many('offered.product-option.description',
        'product', 'Ordered Coverages', order=[('order', 'ASC')],
        states={'invisible': ~Eval('change_coverages_order')},
        delete_missing=True)
    packages = fields.Many2Many('offered.product-package', 'product',
        'package', 'Packages', domain=[('options', 'in', Eval('coverages'))],
        depends=['coverages'])
    currency = fields.Many2One('currency.currency', 'Currency', required=True,
        ondelete='RESTRICT')
    currency_digits = fields.Function(
        fields.Integer('Currency Digits'),
        'on_change_with_currency_digits')
    contract_generator = fields.Many2One('ir.sequence',
        'Contract Number Generator', context={'code': 'offered.product'},
        ondelete='RESTRICT', required=True,
        domain=[('code', '=', 'contract')])
    extra_data_def = fields.Many2Many('offered.product-extra_data',
        'product', 'extra_data_def', 'Extra Data',
        domain=[('kind', 'in', ['contract', 'option'])])
    subscriber_kind = fields.Selection(SUBSCRIBER_KIND, 'Subscriber Kind')
    report_templates = fields.Many2Many('report.template-offered.product',
        'product', 'report_template', 'Report Templates')
    report_style_template = fields.Binary('Report Style')

    @classmethod
    def __setup__(cls):
        super(Product, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('code_uniq', Unique(t, t.code), 'The code must be unique!'),
            ]
        cls.__rpc__.update({'get_product_def': RPC()})

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
    def copy(cls, products, default=None):
        default = {} if default is None else default.copy()
        default.setdefault('coverages', None)
        return super(Product, cls).copy(products, default=default)

    @classmethod
    def is_master_object(cls):
        return True

    @classmethod
    def _export_light(cls):
        return super(Product, cls)._export_light() | {'contract_generator',
            'company', 'currency'}

    @classmethod
    def _export_skips(cls):
        result = super(Product, cls)._export_skips()
        # ordered_coverages should be enough
        result.add('coverages')
        result.add('report_templates')
        return result

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

    @staticmethod
    def default_extra_data():
        res = {}
        for e_d in Pool().get('extra_data').search([('kind', '=', 'product')]):
            res[e_d.name] = e_d.get_default_value(None)
        return res

    def get_valid_coverages(self):
        for coverage in self.coverages:
            if coverage.is_valid():
                yield coverage

    def init_dict_for_rule_engine(self, args):
        if 'product' not in args:
            args['product'] = self

    def get_all_extra_data(self, at_date):
        return getattr(self, 'extra_data', {})

    def get_extra_data_def(self, type_, existing_data, condition_date,
            item_desc=None, coverage=None):
        ExtraData = Pool().get('extra_data')
        all_schemas, possible_schemas = ExtraData.get_extra_data_definitions(
            self, 'extra_data_def', type_, condition_date)
        if item_desc:
            tmp_all, tmp_possible = ExtraData.get_extra_data_definitions(
                item_desc, 'extra_data_def', type_, condition_date)
            all_schemas |= tmp_all
            possible_schemas |= tmp_possible
        if coverage:
            tmp_all, tmp_possible = ExtraData.get_extra_data_definitions(
                coverage, 'extra_data_def', type_, condition_date)
            all_schemas |= tmp_all
            possible_schemas |= tmp_possible
        result = ExtraData.calculate_value_set(possible_schemas, all_schemas,
            existing_data)
        return result

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

    @classmethod
    def get_product_def(cls, code):
        products = cls.search([('code', '=', code)])
        if len(products) == 1:
            return products[0].extract_object('full')

    def get_change_coverages_order(self, name):
        return False

    def get_publishing_values(self):
        result = super(Product, self).get_publishing_values()
        result['name'] = self.name
        result['code'] = self.code
        return result

    def get_report_style_content(self, at_date, template, contract=None):
        if template.template_extension == 'odt':
            return self.report_style_template

    def on_change_with_currency_digits(self, name):
        return self.currency.digits if self.currency else 2


class OptionDescription(model.CoopSQL, model.CoopView, model.TaggedMixin):
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
    extra_data = fields.Dict('extra_data', 'Offered Kind',
        context={'extra_data_kind': 'product'},
        domain=[('kind', '=', 'product')])
    extra_data_string = extra_data.translated('extra_data')
    currency = fields.Many2One('currency.currency', 'Currency', required=True,
        ondelete='RESTRICT')
    currency_digits = fields.Function(
        fields.Integer('Currency Digits'),
        'on_change_with_currency_digits')
    subscription_behaviour = fields.Selection(SUBSCRIPTION_BEHAVIOUR,
        'Subscription Behaviour', sort=False)
    extra_data_def = fields.Many2Many(
        'offered.option.description-extra_data',
        'coverage', 'extra_data_def', 'Extra Data',
        domain=[('kind', 'in', ['contract', 'option'])])
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
        cls._sql_constraints += [
            ('code_uniq', Unique(t, t.code), 'The code must be unique!'),
            ]

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        table = TableHandler(cls, module_name)

        super(OptionDescription, cls).__register__(module_name)

        # Migration from 1.6 Drop Offered inheritance
        if table.column_exist('template'):
            table.drop_column('template')
            table.drop_column('template_behaviour')

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

    @staticmethod
    def default_extra_data():
        res = {}
        for e_d in Pool().get('extra_data').search([('kind', '=', 'product')]):
            res[e_d.name] = e_d.get_default_value(None)
        return res

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

    def get_all_extra_data(self, at_date):
        return getattr(self, 'extra_data', {})

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
        return ', '.join([x.name for x in self.products])

    def on_change_with_currency_digits(self, name):
        return self.currency.digits if self.currency else 2

    @fields.depends('code', 'name')
    def on_change_with_code(self):
        return self.code if self.code else coop_string.slugify(self.name)

    def init_dict_for_rule_engine(self, args):
        args['coverage'] = self

    def calculate_end_date(self, exec_context):
        if self.ending_rule:
            return self.ending_rule[0].calculate_rule(exec_context)


class OptionDescriptionExtraDataRelation(model.CoopSQL):
    'Relation between OptionDescription and Extra Data'

    __name__ = 'offered.option.description-extra_data'

    coverage = fields.Many2One('offered.option.description',
        'Option Description', ondelete='CASCADE')
    extra_data_def = fields.Many2One('extra_data', 'Extra Data',
        ondelete='RESTRICT')


class ProductOptionDescriptionRelation(model.CoopSQL, model.CoopView):
    'Product to Option Description Relation'

    __name__ = 'offered.product-option.description'

    product = fields.Many2One('offered.product', 'Product', ondelete='CASCADE',
        required=True, select=True)
    coverage = fields.Many2One('offered.option.description',
        'Option Description', ondelete='RESTRICT', required=True, select=True)
    order = fields.Integer('Order')


class ProductExtraDataRelation(model.CoopSQL):
    'Relation between Product and Extra Data'

    __name__ = 'offered.product-extra_data'

    product = fields.Many2One('offered.product', 'Product', ondelete='CASCADE')
    extra_data_def = fields.Many2One('extra_data', 'Extra Data',
        ondelete='RESTRICT')


class OptionDescriptionRequired(model.CoopSQL):
    'Option Description Required'

    __name__ = 'offered.option.description.required'

    from_option_desc = fields.Many2One('offered.option.description',
        'From Option Description', ondelete='CASCADE')
    to_option_desc = fields.Many2One('offered.option.description',
        'To Option Description', ondelete='RESTRICT')


class OptionDescriptionExcluded(model.CoopSQL):
    'Option Description Excluded'

    __name__ = 'offered.option.description.excluded'

    from_option_desc = fields.Many2One('offered.option.description',
        'From Option Description', ondelete='CASCADE')
    to_option_desc = fields.Many2One('offered.option.description',
        'To Option Description', ondelete='RESTRICT')

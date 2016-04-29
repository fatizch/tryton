from trytond.pool import Pool
from trytond.model import Unique
from trytond.pyson import Eval, Bool
from trytond.transaction import Transaction
from trytond.rpc import RPC

from trytond.modules.cog_utils import model, utils, fields
from trytond.modules.cog_utils import coop_string
from trytond.modules.currency_cog import ModelCurrency
from trytond.modules.rule_engine import RuleEngineResult

__all__ = [
    'NonExistingRuleKindException',
    'GetResult',
    'Offered',
    'Product',
    'OptionDescription',
    'OptionDescriptionExtraDataRelation',
    'ProductOptionDescriptionRelation',
    'ProductExtraDataRelation',
    'OptionDescriptionRequired',
    'OptionDescriptionExcluded',
    ]

CONFIG_KIND = [
    ('simple', 'Simple'),
    ('advanced', 'Advanced')
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


class Templated(object):
    'Templated'

    __name__ = 'offered.template'

    template = fields.Many2One(None, 'Template',
        domain=[('id', '!=', Eval('id'))], depends=['id'], ondelete='RESTRICT')
    template_behaviour = fields.Selection([
            ('', ''),
            ('pass', 'Add'),
            ('override', 'Remove'),
            ], 'Template Behaviour',
        states={'invisible': ~Eval('template')},
        depends=['template'])

    @fields.depends('template')
    def on_change_template(self):
        if self.template:
            if not self.template_behaviour:
                self.template_behaviour = 'pass'
        else:
            self.template_behaviour = None


class NonExistingRuleKindException(Exception):
    pass


class GetResult(object):
    def get_result(self, target='result', args=None, kind='', path=''):
        # This method is a generic entry point for getting parameters.
        #
        # Arguments are :
        #  - The target value to compute. It is a key which will be used to
        #    decide which data is asked for
        #  - The dict of arguments which will be used by the rule to compute.
        #    Another way to do this would be a link to a method on the caller
        #    which would provide said args on demand.
        #  - The kind will usually be filled, it is a key to finding where
        #    the required data is stored. So if the target is "price", the
        #    kind should be set to "pricing".
        #  - We can use the 'path' arg to specify the way to our data.
        #    Basically, we try to match the first part of path (which looks
        #    like a '.' delimited string ('alpha1.beta3.gamma2')) to one of the
        #    sub-elements of self, then iterate.

        if path:
            # If a path is set, the data we look for is not set on self. So we
            # need to iterate on self's sub-elems.
            #
            # First of all, we need the sub-elems descriptor. This is the
            # result of the get_sub_elem_data method, which returns a tuple
            # with the field name to iterate on as the first element, and
            # this field's field on which to try to match the value.
            sub_elem_data = self.get_sub_elem_data()

            if not sub_elem_data:
                # If it does not exist, someone failed...
                return (None, ['Object %s does not have any sub_data.' % (
                    self.name)])

            path_elems = path.split('.')

            for elem in getattr(self, sub_elem_data[0]):
                # Now we iterate on the specified field
                if path_elems[0] in (
                        getattr(elem, attr) for attr in sub_elem_data[1]):
                    if isinstance(elem, GetResult):
                        return elem.get_result(
                            target, args, kind, '.'.join(path_elems[1:]))
                    return (
                        None, ['Sub element %s of %s cannot get_result !' % (
                            elem.name, self.name)])
            return (None, ['Could not find %s sub element in %s' % (
                path_elems[0], self.name)])

        if kind:
            try:
                good_rule = self.get_good_rule_at_date(args, kind)
            except Exception:
                good_rule = None
            if not good_rule:
                # We did not found any rule matching the specified name
                raise NonExistingRuleKindException
            return good_rule.get_result(target, args)

        # Now we look for our target, as it is at our level
        target_func = getattr(self, 'give_me_' + target)

        result = target_func(args)
        if isinstance(result, RuleEngineResult):
            return result
        if not isinstance(result, tuple) and result is not None:
            return (result, [])
        return result

    def get_sub_elem_data(self):
        # Should be overridden
        return None


class Offered(model.CoopView, GetResult, Templated, model.TaggedMixin):
    'Offered'

    __name__ = 'offered'
    _func_key = 'code'

    code = fields.Char('Code', required=True)
    name = fields.Char('Name', required=True, translate=True)
    start_date = fields.Date('Start Date', required=True)
    end_date = fields.Date('End Date')
    description = fields.Text('Description', translate=True)
    summary = fields.Function(
        fields.Text(
            'Summary', states={'invisible': ~Eval('summary',)}),
        'get_summary')
    currency_digits = fields.Function(
        fields.Integer('Currency Digits'),
        'get_currency_digits')
    extra_data = fields.Dict('extra_data', 'Offered Kind',
        context={'extra_data_kind': 'product'},
        domain=[('kind', '=', 'product')])
    extra_data_string = extra_data.translated('extra_data')
    company = fields.Many2One('company.company', 'Company', required=True,
        ondelete='RESTRICT')

    @classmethod
    def __setup__(cls):
        super(Offered, cls).__setup__()
        cls.template.model_name = cls.__name__

        for field_name in (r for r in dir(cls) if r.endswith('_rules')):
            field = getattr(cls, field_name)
            if not hasattr(field, 'model_name'):
                continue
            if not hasattr(field, 'context'):
                continue
            if field.context is None:
                field.context = {}
            field.context['start_date'] = Eval('start_date')
            field.context['currency_digits'] = Eval('currency_digits')
            if field.depends is None:
                field.depends = []
            field.depends += ['start_date', 'currency_digits']
            if field.states is None:
                field.states = {}
            field.states['readonly'] = ~Bool(Eval('start_date'))

    @staticmethod
    def default_start_date():
        res = Transaction().context.get('start_date')
        if not res:
            res = utils.today()
        return res

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company') or None

    def get_currency_digits(self, name):
        if hasattr(self, 'currency') and self.currency:
            return self.currency.digits
        else:
            return Transaction().context.get('currency_digits')

    @staticmethod
    def default_extra_data():
        good_se = Pool().get('extra_data').search([
                ('kind', '=', 'product')])
        res = {}
        for se in good_se:
            res[se.name] = se.get_default_value(None)
        return res

    def get_good_rule_at_date(self, data, kind):
        # First we got to check that the fields that we will need to calculate
        # which rule is appliable are available in the data dictionnary
        try:
            the_date = data['appliable_conditions_date']
        except KeyError:
            return None

        try:
            # We use the date field from the data argument to search for
            # the good rule.
            # (This is a given way to get a rule from a list, using the
            # applicable date, it could be anything)
            return utils.get_good_version_at_date(
                self, '%s_rules' % kind, the_date)
        except ValueError:
            return None

    @fields.depends('code', 'name')
    def on_change_with_code(self):
        if self.code:
            return self.code
        return coop_string.slugify(self.name)

    def init_dict_for_rule_engine(self, args):
        pass

    @classmethod
    def get_dated_fields(cls):
        return [x for x in cls._fields.keys() if x.endswith('rules')]

    @classmethod
    def validate(cls, instances):
        # Builds a virtual list of all business versions of the offered to be
        # able to validate possible rule dependencies in all possible
        # combinations
        versioned_fields = cls.get_dated_fields()
        for instance in instances:
            values = []
            for field in versioned_fields:
                values += getattr(instance, field)
            dates = set(map(lambda x: x.start_date, values))
            for date in dates:
                data = dict([
                        (x, utils.get_good_version_at_date(instance, x, date))
                        for x in versioned_fields])
                instance.validate_consistency(data)

    def validate_consistency(self, data):
        pass

    def get_all_extra_data(self, at_date):
        return getattr(self, 'extra_data', {})


class Product(model.CoopSQL, Offered):
    'Product'

    __name__ = 'offered.product'
    _func_key = 'code'

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

    def get_valid_coverages(self):
        for coverage in self.coverages:
            if coverage.is_valid():
                yield coverage

    def init_dict_for_rule_engine(self, args):
        super(Product, self).init_dict_for_rule_engine(args)
        if 'product' not in args:
            args['product'] = self

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

    @classmethod
    def default_currency(cls):
        return ModelCurrency.default_currency()

    def give_me_new_contract_number(self, args=None):
        return (self.contract_generator.get_id(self.contract_generator.id)
            if self.contract_generator else '')

    def give_me_extra_data_ids_aggregate(self, args):
        if 'dd_args' not in args:
            return [], []
        res = set()
        errs = []
        for opt in self.coverages:
            result, errors = opt.get_result(
                'extra_data_ids_aggregate',
                args)
            map(lambda x: res.add(x), result)
            errs += errors
        return list(res), errs

    def give_me_extra_data_getter(self, args):
        if 'dd_args' not in args:
            return [], []
        dd_args = args['dd_args']
        if 'path' not in dd_args:
            if 'options' not in dd_args:
                return self.give_me_extra_data_ids(args)
            dd_args['path'] = 'all'
        return self.give_me_extra_data_ids_aggregate(args)

    def get_currency(self):
        return self.currency

    def give_me_calculated_extra_datas(self, args):
        # We prepare the call to the 'calculate_value_set' API.
        # It needs the following parameters:
        #  - The list of the schemas it must look for
        #  - The list of all the schemas in the tree. This list should
        #    contain all the schemas from the first list
        #  - All the values available for all relevent schemas
        if 'contract' not in args or 'date' not in args:
            raise Exception('Expected contract and date in args, got %s' % (
                str([k for k in args.iterkeys()])))
        all_schemas, possible_schemas = self.get_extra_data_for_exec(args)
        if 'sub_elem' not in args:
            for option in args['contract'].options:
                if not option.coverage:
                    continue
                coverage_all, coverage_possible = \
                    option.coverage.get_extra_data_for_exec(args)
                all_schemas |= coverage_all
                possible_schemas |= coverage_possible
        else:
            coverage = args['coverage']
            coverage_all, coverage_possible = \
                coverage.get_extra_data_for_exec(args)
            all_schemas |= coverage_all
            possible_schemas |= coverage_possible
        existing_data = {}
        if args['contract'].extra_data:
            existing_data.update(args['contract'].extra_data)
        key = None
        if 'option' in args:
            key = 'option'
        elif 'sub_elem' in args:
            key = 'sub_elem'
        elif 'contract' in args:
            key = 'contract'
        if key:
            existing_data.update(args[key].get_all_extra_data(
                args['date']))
        ExtraData = Pool().get('extra_data')
        result = ExtraData.calculate_value_set(
            possible_schemas, all_schemas, existing_data, args)
        return result, ()

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

    @staticmethod
    def default_subscriber_kind():
        return 'all'

    @classmethod
    def get_var_names_for_full_extract(cls):
        res = super(Product, cls).get_var_names_for_full_extract()
        res.extend(['extra_data_def',
            'coverages', 'description', 'subscriber_kind',
            ('currency', 'light')])
        return res

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


class OptionDescription(model.CoopSQL, Offered):
    'OptionDescription'

    __name__ = 'offered.option.description'
    _func_key = 'code'

    currency = fields.Many2One('currency.currency', 'Currency', required=True,
        ondelete='RESTRICT')
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

    def calculate_end_date(self, exec_context):
        if self.ending_rule:
            return self.ending_rule[0].calculate(exec_context)

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
    def __setup__(cls):
        super(OptionDescription, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('code_uniq', Unique(t, t.code), 'The code must be unique!'),
            ]

    @classmethod
    def copy(cls, options, default=None):
        default = {} if default is None else default.copy()
        default.setdefault('products', None)
        return super(OptionDescription, cls).copy(options, default=default)

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

    @classmethod
    def default_currency(cls):
        return ModelCurrency.default_currency()

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

    def give_me_extra_data_ids_aggregate(self, args):
        if 'dd_args' not in args:
            return [], []
        dd_args = args['dd_args']
        if not('options' in dd_args and dd_args['options'] != '' and
                self.code in dd_args['options'].split(';')):
            return [], []
        return self.get_extra_data_def(
            [dd_args['kind']], args['date']), []

    @staticmethod
    def default_subscription_behaviour():
        return 'mandatory'

    def get_currency(self):
        return self.currency

    @classmethod
    def get_var_names_for_full_extract(cls):
        res = super(OptionDescription, cls).get_var_names_for_full_extract()
        res.extend(['extra_data_def', 'description',
            'subscription_behaviour'])
        return res

    def init_dict_for_rule_engine(self, args):
        super(OptionDescription, self).init_dict_for_rule_engine(args)
        args['coverage'] = self

    def get_publishing_values(self):
        result = super(OptionDescription, self).get_publishing_values()
        result['name'] = self.name
        result['code'] = self.code
        return result

    def on_change_with_is_service(self, name=None):
        return True

    @fields.depends('products')
    def on_change_with_products_name(self, name=None):
        return ', '.join([x.name for x in self.products])

    @staticmethod
    def default_is_service():
        return True


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

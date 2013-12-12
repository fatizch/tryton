import copy

from trytond.pool import Pool
from trytond.pyson import Eval, Bool
from trytond.transaction import Transaction
from trytond.rpc import RPC

from trytond.modules.coop_utils import model, business, utils, fields
from trytond.modules.coop_utils import coop_string
from trytond.modules.coop_currency import ModelCurrency
from trytond.modules.offered import EligibilityResultLine
from trytond.modules.rule_engine import RuleEngineResult

__all__ = [
    'NonExistingRuleKindException',
    'GetResult',
    'Offered',
    'Product',
    'ProductOptionsCoverage',
    'ProductComplementaryDataRelation',
    ]

CONFIG_KIND = [
    ('simple', 'Simple'),
    ('advanced', 'Advanced')
    ]

TEMPLATE_BEHAVIOUR = [
    ('', ''),
    ('pass', 'Add'),
    ('override', 'Remove'),
    ]

SUBSCRIBER_KIND = [
    ('all', 'All'),
    ('person', 'Person'),
    ('company', 'Company'),
    ]

DEF_CUR_DIG = 2


class Templated(object):
    'Templated Class'

    __name__ = 'offered.templated'

    template = fields.Many2One(
        None, 'Template',
        domain=[('id', '!=', Eval('id'))],
        depends=['id'],
        on_change=['template'])
    template_behaviour = fields.Selection(
        TEMPLATE_BEHAVIOUR,
        'Template Behaviour',
        states={
            'invisible': ~Eval('template'),
        },
        depends=['template'])

    def on_change_template(self):
        if hasattr(self, 'template') and self.template:
            if not hasattr(self, 'template_behaviour') or \
                    not self.template_behaviour:
                return {'template_behaviour': 'pass'}
        else:
            return {'template_behaviour': None}


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
        if not isinstance(result, tuple) and not result is None:
            return (result, [])
        return result

    def get_sub_elem_data(self):
        # Should be overridden
        return None


class Offered(model.CoopView, GetResult, Templated):
    'Offered'

    __name__ = 'offered'
    _export_name = 'code'

    code = fields.Char('Code', required=True, select=1,
        on_change_with=['code', 'name'])
    name = fields.Char('Name', required=True, select=1, translate=True)
    start_date = fields.Date('Start Date', required=True, select=1)
    end_date = fields.Date('End Date')
    description = fields.Text('Description', translate=True)
    summary = fields.Function(
        fields.Text(
            'Summary', states={'invisible': ~Eval('summary',)}),
        'get_summary')
    currency_digits = fields.Function(
        fields.Integer('Currency Digits'),
        'get_currency_digits')
    complementary_data = fields.Dict(
        'extra_data', 'Offered Kind',
        context={'complementary_data_kind': 'product'},
        domain=[('kind', '=', 'product')],
        on_change_with=['complementary_data'])
    company = fields.Many2One('company.company', 'Company', required=True,
        ondelete="RESTRICT")

    @classmethod
    def __setup__(cls):
        super(Offered, cls).__setup__()
        cls.template = copy.copy(cls.template)
        cls.template.model_name = cls.__name__

        for field_name in (r for r in dir(cls) if r.endswith('_rules')):
            field = getattr(cls, field_name)
            if not hasattr(field, 'model_name'):
                continue
            cur_attr = copy.copy(field)
            if not hasattr(cur_attr, 'context'):
                continue
            if cur_attr.context is None:
                cur_attr.context = {}
            cur_attr.context['start_date'] = Eval('start_date')
            cur_attr.context['currency_digits'] = Eval('currency_digits')
            if cur_attr.depends is None:
                cur_attr.depends = []
            utils.extend_inexisting(
                cur_attr.depends, ['start_date', 'currency_digits'])
            if cur_attr.states is None:
                cur_attr.states = {}
            cur_attr.states['readonly'] = ~Bool(Eval('start_date'))

            setattr(cls, field_name, cur_attr)

    @staticmethod
    def default_start_date():
        res = Transaction().context.get('start_date')
        if not res:
            res = utils.today()
        return res

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company') or None

    @classmethod
    def get_summary(cls, offereds, name=None, at_date=None, lang=None):
        res = {}
        for offered in offereds:
            res[offered.id] = ''
        return res

    def get_currency_digits(self, name):
        if hasattr(self, 'currency') and self.currency:
            return self.currency.digits
        else:
            return Transaction().context.get('currency_digits')

    @staticmethod
    def default_complementary_data():
        good_se = Pool().get('extra_data').search([
                ('kind', '=', 'product')])
        res = {}
        for se in good_se:
            res[se.name] = se.get_default_value(None)
        return res

    def get_complementary_data_def(self, kinds=None, at_date=None):
        return [
            x for x in self.complementary_data_def
            if x.valid_at_date(at_date) and (not kinds or x.kind in kinds)]

    def get_cmpl_data_looking_for_what(self, args):
        return 'contract' if not 'sub_elem' in args else 'sub_elem'

    def get_compl_data_for_exec(self, args):
        looking_for = self.get_cmpl_data_looking_for_what(args)
        all_schemas = set(self.get_complementary_data_def(
            ('contract', looking_for), args['date']))
        if looking_for:
            possible_schemas = set(self.get_complementary_data_def(
                (looking_for), args['date']))
        else:
            possible_schemas = set([])
        return all_schemas, possible_schemas

    def on_change_with_complementary_data(self):
        if not hasattr(self, 'complementary_data_def'):
            return {}
        ComplementaryData = Pool().get('extra_data')
        schemas = ComplementaryData.search([
            'name', 'in', [k for k in self.complementary_data_def.iterkeys()]])
        if not schemas:
            return {}
        result = copy.copy(self.complementary_data_def)
        for schema in schemas:
            schema.update_field_value(result)
        return result

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

    def on_change_with_code(self):
        if self.code:
            return self.code
        return coop_string.remove_blank_and_invalid_char(self.name)

    def init_dict_for_rule_engine(self, args):
        pass


class Product(model.CoopSQL, Offered):
    'Product'

    __name__ = 'offered.product'

    kind = fields.Selection([('', ''), ('default', 'Default')],
        'Product Kind')
    coverages = fields.Many2Many('offered.product-options-coverage',
        'product', 'coverage', 'Coverages',
        domain=[
            ('currency', '=', Eval('currency')),
            ('kind', '=', Eval('kind')),
            ('company', '=', Eval('company')),
            ], depends=['currency', 'kind', 'company'])
    currency = fields.Many2One('currency.currency', 'Currency', required=True)
    contract_generator = fields.Many2One('ir.sequence',
        'Contract Number Generator', context={'code': 'offered.product'},
        ondelete='RESTRICT', required=True)
    complementary_data_def = fields.Many2Many(
        'offered.product-extra_data',
        'product', 'complementary_data_def', 'Complementary Data',
        domain=[('kind', 'in', ['contract', 'sub_elem'])])
    subscriber_kind = fields.Selection(SUBSCRIBER_KIND, 'Subscriber Kind')

    @classmethod
    def __setup__(cls):
        super(Product, cls).__setup__()
        cls._sql_constraints += [
            ('code_uniq', 'UNIQUE(code)', 'The code must be unique!'),
            ]
        cls.__rpc__.update({'get_product_def': RPC()})

    def get_valid_coverages(self):
        for coverage in self.coverages:
            if coverage.is_valid():
                yield coverage

    def init_dict_for_rule_engine(self, args):
        super(Product, self).init_dict_for_rule_engine(args)
        if not 'product' in args:
            args['product'] = self

    @classmethod
    def default_currency(cls):
        return ModelCurrency.default_currency()

    def give_me_new_contract_number(self, args=None):
        return (self.contract_generator.get_id(self.contract_generator.id)
            if self.contract_generator else '')

    def give_me_complementary_data_ids_aggregate(self, args):
        if not 'dd_args' in args:
            return [], []
        res = set()
        errs = []
        for opt in self.coverages:
            result, errors = opt.get_result(
                'complementary_data_ids_aggregate',
                args)
            map(lambda x: res.add(x), result)
            errs += errors
        return list(res), errs

    def give_me_complementary_data_getter(self, args):
        if not 'dd_args' in args:
            return [], []
        dd_args = args['dd_args']
        if not 'path' in dd_args:
            if not 'options' in dd_args:
                return self.give_me_complementary_data_ids(args)
            dd_args['path'] = 'all'
        return self.give_me_complementary_data_ids_aggregate(args)

    def get_currency(self):
        return self.currency

    def give_me_calculated_complementary_datas(self, args):
        # We prepare the call to the 'calculate_value_set' API.
        # It needs the following parameters:
        #  - The list of the schemas it must look for
        #  - The list of all the schemas in the tree. This list should
        #    contain all the schemas from the first list
        #  - All the values available for all relevent schemas
        if not 'contract' in args or not 'date' in args:
            raise Exception('Expected contract and date in args, got %s' % (
                str([k for k in args.iterkeys()])))
        all_schemas, possible_schemas = self.get_compl_data_for_exec(args)
        if not 'sub_elem' in args:
            for coverage in args['contract'].get_active_coverages_at_date(
                    args['date']):
                coverage_all, coverage_possible = \
                    coverage.get_compl_data_for_exec(args)
                all_schemas |= coverage_all
                possible_schemas |= coverage_possible
        else:
            coverage = args['coverage']
            coverage_all, coverage_possible = \
                coverage.get_compl_data_for_exec(args)
            all_schemas |= coverage_all
            possible_schemas |= coverage_possible
        existing_data = {}
        if args['contract'].complementary_data:
            existing_data.update(args['contract'].complementary_data)
        key = None
        if 'data' in args:
            key = 'data'
        elif 'sub_elem' in args:
            key = 'sub_elem'
        elif 'contract' in args:
            key = 'contract'
        if key:
            existing_data.update(args[key].get_all_complementary_data(
                args['date']))
        ComplementaryData = Pool().get('extra_data')
        result = ComplementaryData.calculate_value_set(
            possible_schemas, all_schemas, existing_data, args)
        return result, ()

    def give_me_eligibility(self, args):
        # First of all, we look for a subscriber data in the args and update
        # the args dictionnary for sub values.
        try:
            business.update_args_with_subscriber(args)
        except business.ArgsDoNotMatchException:
            # If no Subscriber is found, automatic refusal
            return (EligibilityResultLine(
                False, ['Subscriber not defined in args']), [])

        res, errs = self.check_subscriber_kind(args)
        if not res:
            return EligibilityResultLine(False, errs)
        try:
            res = self.get_result('eligibility', args, kind='eligibility')
        except NonExistingRuleKindException:
            return (EligibilityResultLine(True), [])
        return res

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
        res.extend(['complementary_data_def',
            'coverages', 'description', 'subscriber_kind',
            ('currency', 'light')])
        return res

    @classmethod
    def get_product_def(cls, code):
        products = cls.search([('code', '=', code)])
        if len(products) == 1:
            return products[0].extract_object('full')


class ProductOptionsCoverage(model.CoopSQL):
    'Define Product - Coverage relations'

    __name__ = 'offered.product-options-coverage'

    product = fields.Many2One(
        'offered.product', 'Product',
        select=1, required=True, ondelete='CASCADE')
    coverage = fields.Many2One(
        'offered.option.description', 'Coverage',
        select=1, required=True, ondelete='RESTRICT')


class ProductComplementaryDataRelation(model.CoopSQL):
    'Relation between Product and Complementary Data'

    __name__ = 'offered.product-extra_data'

    product = fields.Many2One(
        'offered.product', 'Product', ondelete='CASCADE')
    complementary_data_def = fields.Many2One(
        'extra_data',
        'Complementary Data', ondelete='RESTRICT')

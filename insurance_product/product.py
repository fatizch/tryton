#-*- coding:utf-8 -*-
import copy

from trytond.model import fields as fields
from trytond.pool import Pool
from trytond.pyson import Eval, Bool
from trytond.transaction import Transaction
from trytond.rpc import RPC

from trytond.modules.coop_utils import CoopView, CoopSQL, GetResult
from trytond.modules.coop_utils import utils as utils
from trytond.modules.insurance_product import PricingResultLine
from trytond.modules.insurance_product import EligibilityResultLine
from trytond.modules.coop_utils import One2ManyDomain, WithAbstract
from trytond.modules.coop_utils import add_frequency, number_of_days_between
from trytond.modules.coop_utils import business, NonExistingManagerException
from trytond.modules.coop_utils import update_args_with_subscriber, \
    ArgsDoNotMatchException, get_those_objects

__all__ = ['Offered', 'Coverage', 'Product', 'ProductOptionsCoverage',
           'BusinessRuleManager', 'GenericBusinessRule', 'BusinessRuleRoot',
           'PricingRule', 'PriceCalculator', 'PricingData',
           'EligibilityRule', 'EligibilityRelationKind',
           'Benefit', 'BenefitRule', 'ReserveRule', 'CoverageAmountRule']

CONFIG_KIND = [
    ('simple', 'Simple'),
    ('rule', 'Rule Engine')
    ]


SUBSCRIBER_CLASSES = [
    ('party.person', 'Person'),
    ('party.company', 'Company'),
    ('party.party', 'All'),
    ]


PRICING_LINE_KINDS = [
    ('base', 'Base Price'),
    ('tax', 'Tax'),
    ('fee', 'Fee')
    ]


PRICING_FREQUENCY = [
    ('yearly', 'Yearly'),
    ('half-yearly', 'Half Yearly'),
    ('quarterly', 'Quarterly'),
    ('monthly', 'Monthly')
    ]

TEMPLATE_BEHAVIOUR = [
    ('override', 'Override'),
    ('add', 'Add'),
    ('remove', 'Remove'),
    ('validate', 'Validate'),
    ]

FAMILIES_EXTS = {
    'life': 'extension_life'}


class Templated(object):
    'Templated Class'

    __name__ = 'ins_product.templated'

    template = fields.Many2One(None, 'Template',
        domain=[('id', '!=', Eval('id'))],
        depends=['id'],
        on_change=['template'])
    template_behaviour = fields.Selection(
        TEMPLATE_BEHAVIOUR,
        'Template Behaviour',
        states={'readonly': ~Eval('template')},
        depends=['template'])

    def on_change_template(self):
        if hasattr(self, 'template') and self.template:
            if not hasattr(self, 'template_behaviour') or \
                    not self.template_behaviour:
                return {'template_behaviour': 'override'}
        else:
            return {'template_behaviour': None}


class Offered(CoopView, GetResult, Templated):
    'Offered'

    __name__ = 'ins_product.offered'

    code = fields.Char('Code', size=10, required=True, select=1)
    name = fields.Char('Name', required=True, select=1)
    start_date = fields.Date('Start Date', required=True, select=1)
    end_date = fields.Date('End Date')
    description = fields.Text('Description')
    #All mgr var must be the same as the business rule class and ends with mgr
    pricing_mgr = One2ManyDomain('ins_product.business_rule_manager',
        'offered', 'Pricing Manager')
    eligibility_mgr = One2ManyDomain('ins_product.business_rule_manager',
        'offered', 'Eligibility Manager')

    @classmethod
    def __setup__(cls):
        super(Offered, cls).__setup__()
        for field_name in (mgr for mgr in dir(cls) if mgr.endswith('mgr')):
            cur_attr = copy.copy(getattr(cls, field_name))
            if not hasattr(cur_attr, 'context'):
                continue
            if cur_attr.context is None:
                cur_attr.context = {}
            cur_attr.context['start_date'] = Eval('start_date')

            if cur_attr.states is None:
                cur_attr.states = {}
            cur_attr.states['readonly'] = ~Bool(Eval('start_date'))

            if not hasattr(cur_attr, 'model_name'):
                continue
            cur_attr.domain = [('business_rules.kind', '=',
                    '%s.%s_rule' %
                        (utils.get_module_name(cls),
                        field_name.split('_mgr')[0]))]
            cur_attr.size = 1
            cur_attr = copy.copy(cur_attr)
            setattr(cls, field_name, cur_attr)

        cls.template = copy.copy(cls.template)
        cls.template.model_name = cls.__name__

    @staticmethod
    def default_start_date():
        res = Transaction().context.get('start_date')
        if not res:
            date = Pool().get('ir.date').today()
            res = date
        return res

    def get_name_for_billing(self):
        return self.name


class Coverage(CoopSQL, Offered):
    'Coverage'

    __name__ = 'ins_product.coverage'

    insurer = fields.Many2One('party.insurer', 'Insurer')
    family = fields.Selection([('life', 'Life')], 'Family',
        required=True)
    benefits = fields.One2Many('ins_product.benefit', 'coverage', 'Benefits',
        context={'start_date': Eval('start_date')},
        states={'readonly': ~Bool(Eval('start_date'))})
    currency = fields.Many2One('currency.currency', 'Currency', required=True)
    coverage_amount_mgr = One2ManyDomain('ins_product.business_rule_manager',
        'offered', 'Coverage Amount Manager')

    @classmethod
    def __setup__(cls):
        super(Coverage, cls).__setup__()
        cls._sql_constraints += [
            ('code_uniq', 'UNIQUE(code)', 'The code must be unique!'),
        ]

    def give_me_price(self, args):
        # This method is one of the core of the pricing system. It asks for the
        # price for the self depending on the contrat that is given as an
        # argument.
        data_dict, errs = utils.get_data_from_dict(['contract', 'date'], args)
        if errs:
            # No contract means no price.
            return (None, errs)
        contract = data_dict['contract']
        date = data_dict['date']

        # We need to chack that self is part of the subscribed coverages of the
        # contract.
        coverages = contract.get_active_coverages_at_date(date)
        res = PricingResultLine(name=self.name)
        if self in coverages:
            # The first part of the pricing is the price at the coverage level.
            # It is computed by the pricing manager, so we just need to forward
            # the request.
            _res, _errs = self.get_result('price', args, manager='pricing')
            if _res:
                # If a result exists, we give it a name and add it to the main
                # result
                for_option = contract.get_option_for_coverage_at_date(
                    self, date)
                if for_option:
                    if for_option.id:
                        _res.on_object = '%s,%s' % (
                            for_option.__name__, for_option.id)
                    else:
                        _res.name = 'Global Price'
                res += _res
                res.on_object = '%s,%s' % (
                    self.__name__, self.id)
            # We always append the errors (if any).
            errs += _errs

            # Now it is time to price the covered elements of the contract.
            # Note that they might have a role in the Base Price computation,
            # depending on the algorithm that is used.
            #
            # What we compute now is the part of the price that is associated
            # to each of the covered elements at the given date
            for covered, covered_data in self.give_me_covered_elements_at_date(
                    args):
                # Now we need to set a new argument before forwarding
                # the request to the manager, which is the covered
                # element it must work on.
                tmp_args = args
                tmp_args['for_covered'] = covered

                # And we finally call the manager for the price
                _res, _errs = self.get_result(
                    'sub_elem_price',
                    tmp_args,
                    manager='pricing')
                if _res and _res.value:
                    # Basically we set name = covered.product_specific
                    # .person.name, but 'product_specific' is a
                    # Reference field and is not automatically turned
                    # into a browse object.
                    # Should be done later by tryton.
                    _res.name = covered.get_name_for_info()
                    if covered_data.id:
                        _res.on_object = '%s,%s' % (
                            covered_data.__name__,
                            covered_data.id)
                    res += _res
                    errs += _errs
            errs = list(set(errs))
            if 'Could not find a matching manager' in errs:
                errs.remove('Could not find a matching manager')
            return (res, list(set(errs)))
        return (None, [])

    def get_dates(self):
        # This is a temporary functionnality that is provided to ease the
        # checking of the pricing calculations.
        # In 'real life', it is not systematic to update the pricing when a new
        # version of the rule is defined.
        res = set()
        if self.pricing_mgr and len(self.pricing_mgr) == 1:
            for rule in self.pricing_mgr[0].business_rules:
                res.add(rule.start_date)
        return res

    def give_me_eligibility(self, args):
        try:
            res = self.get_result('eligibility', args, manager='eligibility')
        except utils.NonExistingManagerException:
            return (EligibilityResultLine(True), [])
        return res

    def give_me_sub_elem_eligibility(self, args):
        try:
            res = self.get_result(
                'sub_elem_eligibility', args, manager='eligibility')
        except utils.NonExistingManagerException:
            return (EligibilityResultLine(True), [])
        return res

    @staticmethod
    def default_currency():
        return business.get_default_currency()

    def get_currency_digits(self, name):
        if self.currency:
            return self.currency.digits

    @staticmethod
    def default_family():
        return 'life'

    def give_me_family(self, args):
        return (self.family, [])

    def give_me_extension_name(self, args):
        return FAMILIES_EXTS[self.give_me_family(args)[0]]

    def give_me_covered_elements_at_date(self, args):
        contract = args['contract']
        date = args['date']
        res = []
        good_ext = self.give_me_extension_name(args)
        if not hasattr(contract, good_ext):
            return []
        for covered in getattr(contract, good_ext).covered_elements:
            # We must check that the current covered element is
            # covered by self.
            for covered_data in covered.covered_data:
                for_coverage = utils.convert_ref_to_obj(
                    covered_data.for_coverage)
                if not for_coverage.code == self.code:
                    continue

                # And that this coverage is effective at the requested
                # computation date.
                if not (date >= covered_data.start_date and
                        (not hasattr(covered_data, 'end_date') or
                            covered_data.end_date is None or
                            covered_data.end_date < date)):
                    continue
                res.append((covered, covered_data))
        return res

    def is_valid(self):
        if self.template_behaviour == 'remove':
            return False
        return True


class Product(CoopSQL, Offered):
    'Product'

    __name__ = 'ins_product.product'

    options = fields.Many2Many('ins_product.product-options-coverage',
        'product', 'coverage', 'Options',
        domain=[('currency', '=', Eval('currency'))],
        depends=['currency'])
    currency = fields.Many2One('currency.currency', 'Currency', required=True)

    @classmethod
    def __setup__(cls):
        super(Product, cls).__setup__()
        cls._sql_constraints += [
            ('code_uniq', 'UNIQUE(code)', 'The code must be unique!'),
        ]

    def get_valid_options(self):
        for option in self.options:
            if option.is_valid():
                yield option

    def get_sub_elem_data(self):
        # This method is used by the get_result method to know where to look
        # for sub-elements to parse and what fields can be used for key
        # matching
        #
        # Here it states that Product objects have a list of 'options' which
        # implements the GetResult class, and on which we might use 'code' or
        # 'name' as keys.
        return ('options', ['code', 'name'])

    def update_args(self, args):
        # We might need the product while computing the options
        if not 'product' in args:
            args['product'] = self

    def give_me_options_price(self, args):
        # Getting the options price is easy : just loop and append the results
        errs = []
        res = []

        self.update_args(args)
        for option in self.get_valid_options():
            _res, _errs = option.get_result('price', args)
            if _res:
                res.append(_res)
            errs += _errs
        return (res, errs)

    def give_me_product_price(self, args):
        # There is a pricing manager on the products so we can just forward the
        # request.
        try:
            res = self.get_result('price', args, manager='pricing')
        except utils.NonExistingManagerException:
            res = (False, [])
        if not res[0]:
            res = (PricingResultLine(), res[1])
        data_dict, errs = utils.get_data_from_dict(['contract'], args)
        if errs:
            # No contract means no price.
            return (None, errs)
        contract = data_dict['contract']
        res[0].name = 'Product Global Price'
        if contract.id:
            res[0].on_object = '%s,%s' % (self.__name__, self.id)
        try:
            res[1].remove('Business Manager pricing does not exist on %s'
                % self.name)
        except ValueError:
            pass
        return [res[0]], res[1]

    def give_me_total_price(self, args):
        # Total price is the sum of Options price and Product price
        (p_price, errs_product) = self.give_me_product_price(args)
        (o_price, errs_options) = self.give_me_options_price(args)

        lines = []

        for line in p_price + o_price:
            if line.value == 0:
                continue
            lines.append(line)

        return (lines, errs_product + errs_options)

    def give_me_eligibility(self, args):
        try:
            res = self.get_result('eligibility', args, manager='eligibility')
        except utils.NonExistingManagerException:
            return (EligibilityResultLine(True), [])
        return res

    def give_me_families(self, args):
        self.update_args(args)
        result = []
        errors = []
        for option in self.get_valid_options():
            res, errs = option.get_result('family', args)
            result += res
            errors += errs
        return (result, errors)

    def give_me_frequency(self, args):
        if not 'date' in args:
            raise Exception('A date must be provided')
        date = args['date']
        try:
            return self.get_result('frequency', args, manager='pricing')
        except NonExistingManagerException:
            pass
        for coverage in self.get_valid_options():
            try:
                return coverage.get_result(
                    'frequency', args, manager='pricing')
            except NonExistingManagerException:
                pass
        return 'yearly', []

    @staticmethod
    def default_currency():
        return business.get_default_currency()

    def get_currency_digits(self, name):
        if self.currency:
            return self.currency.digits


class ProductOptionsCoverage(CoopSQL):
    'Define Product - Coverage relations'

    __name__ = 'ins_product.product-options-coverage'

    product = fields.Many2One('ins_product.product',
        'Product', select=1, required=True, ondelete='CASCADE')
    coverage = fields.Many2One('ins_product.coverage',
        'Coverage', select=1, required=True, ondelete='CASCADE')


class BusinessRuleManager(CoopSQL, CoopView, GetResult, Templated):
    'Business Rule Manager'

    __name__ = 'ins_product.business_rule_manager'

    offered = fields.Reference('Offered', selection='get_offered_models')
    business_rules = fields.One2Many('ins_product.generic_business_rule',
        'manager', 'Business Rules')  # on_change=['business_rules'])

    @classmethod
    def __setup__(cls):
        super(BusinessRuleManager, cls).__setup__()
        cls.template = copy.copy(cls.template)
        cls.template.model_name = cls.__name__
        cls.__rpc__.update({'get_offered_models': RPC()})

    @staticmethod
    def get_offered_models():
        return utils.get_descendents(Offered)

#    def on_change_business_rules(self):
#        res = {'business_rules': {}}
#        res['business_rules'].setdefault('update', [])
#        for business_rule1 in self.business_rules:
#            #the idea is to always set the end_date
#            #to the according next start_date
#            for business_rule2 in self.business_rules:
#                if (business_rule1 != business_rule2 and
#                    business_rule2['start_date'] is not None
#                    and business_rule1['start_date'] is not None and
#                    business_rule2['start_date'] >
#                    business_rule1['start_date']
#                    and (business_rule1['end_date'] is None or
#                         business_rule1['end_date'] >=
#                         business_rule2['start_date'])):
#                    end_date = (business_rule2['start_date']
#                               - datetime.timedelta(days=1))
#                    res['business_rules']['update'].append({
#                        'id': business_rule1.id,
#                        'end_date': end_date})
#
#            #if we change the start_date to a date after the end_date,
#            #we reinitialize the end_date
#            if (business_rule1['end_date'] is not None
#                and business_rule1['start_date'] is not None
#                and business_rule1['end_date'] <
#                    business_rule1['start_date']):
#                res['business_rules']['update'].append({
#                        'id': business_rule1.id,
#                        'end_date': None})
#        return res

    def get_good_rule_at_date(self, data):
        # First we got to check that the fields that we will need to calculate
        # which rule is appliable are available in the data dictionnary
        try:
            the_date = data['date']
        except KeyError:
            return None

        try:
            # We use the date field from the data argument to search for
            # the good rule.
            # (This is a given way to get a rule from a list, using the
            # applicable date, it could be anything)
            return utils.get_good_version_at_date(self, 'business_rules',
                the_date)
        except ValueError, _exception:
            return None

    #Used????
    def get_rec_name(self, name):
        res = ''
        if self.business_rules and len(self.business_rules) > 0:
            res = self.business_rules[0].kind
        if res != '':
            res += ' '
        res += '(%s)' % self.id
        return res

    def get_currency_digits(self, name):
        if self.offered:
            return self.offered.get_currency_digits(name)
        return 2


class GenericBusinessRule(CoopSQL, CoopView):
    'Generic Business Rule'

    __name__ = 'ins_product.generic_business_rule'

    kind = fields.Selection('get_kind', 'Kind',
                            required=True, on_change=['kind'])
    manager = fields.Many2One('ins_product.business_rule_manager', 'Manager',
        ondelete='CASCADE')
    start_date = fields.Date('From Date', required=True)
    end_date = fields.Date('To Date')
    is_current = fields.Function(fields.Boolean('Is current'),
        'get_is_current')
    pricing_rule = fields.One2Many('ins_product.pricing_rule',
        'generic_rule', 'Pricing Rule', size=1)
    eligibility_rule = fields.One2Many('ins_product.eligibility_rule',
        'generic_rule', 'Eligibility Rule', size=1)
    benefit_rule = fields.One2Many('ins_product.benefit_rule',
        'generic_rule', 'Benefit Rule', size=1)
    reserve_rule = fields.One2Many('ins_product.reserve_rule',
        'generic_rule', 'Reserve Rule', size=1)
    coverage_amount_rule = fields.One2Many('ins_product.coverage_amount_rule',
        'generic_rule', 'Coverage Amount Rule', size=1)

    @classmethod
    def view_header_get(cls, value, view_type='form'):
        resource = Transaction().context.get('resource')
        if resource:
            model_name, record_id = resource.split(',', 1)
            Resource = Pool().get(model_name)
            record = Resource(int(record_id))
            if hasattr(record, 'kind') and record.kind:
                return record.kind
        return super(GenericBusinessRule, cls).view_header_get(
            value, view_type)

    def get_rec_name(self, name):
        return self.kind

    @classmethod
    def __setup__(cls):
        super(GenericBusinessRule, cls).__setup__()
        cls.kind = copy.copy(cls.kind)
        for field_name in (rule for rule in dir(cls) if rule.endswith('rule')):
            attr = copy.copy(getattr(cls, field_name))
            if not hasattr(attr, 'model_name'):
                continue
            if cls.kind.on_change is None:
                cls.kind.on_change = []
            if field_name not in cls.kind.on_change:
                cls.kind.on_change += [field_name]

            attr.states = {
                'invisible': (Eval('kind') != attr.model_name)}
            setattr(cls, field_name, attr)

        cls._order.insert(0, ('start_date', 'ASC'))
        cls._constraints += [('check_dates', 'businessrule_overlaps')]
        cls._error_messages.update({'businessrule_overlaps':
            'You can not have 2 business rules that overlaps!'})

    def on_change_kind(self):
        res = {}
        for field_name, field in self._columns.iteritems():
            if not (hasattr(field, 'model_name')
                and getattr(field, 'model_name').endswith('_rule')
                and (not getattr(self, field_name)
                    or len(getattr(self, field_name) == 0))):
                continue

            if field.model_name != self.kind:
                continue

            res[field_name] = {}
            #We add in the dictionary all default values
            Rule = Pool().get(field.model_name)
            fields_names = list(x for x in set(Rule._fields.keys()
                    + Rule._inherit_fields.keys())
            if x not in ['id', 'create_uid', 'create_date',
                'write_uid', 'write_date'])
            res[field_name]['add'] = [Rule.default_get(fields_names)]
            #res[field_name]['add'] = [{}]
        return res

    @staticmethod
    def get_kind():
        return utils.get_descendents_name(BusinessRuleRoot)

    def get_is_current(self, name):
        #first we need the model for the manager (depends on the module used
        if not hasattr(self.__class__, 'manager'):
            return False
        manager_attr = getattr(self.__class__, 'manager')
        if not hasattr(manager_attr, 'model_name'):
            return False
        BRM = Pool().get(manager_attr.model_name)
        date = Pool().get('ir.date').today()
        return self == BRM.get_good_rule_at_date(self.manager,
                {'date': date})

    def check_dates(self):
        cursor = Transaction().cursor
        cursor.execute('SELECT id ' \
                'FROM ' + self._table + ' ' \
                'WHERE ((start_date <= %s AND end_date >= %s) ' \
                        'OR (start_date <= %s AND end_date >= %s) ' \
                        'OR (start_date >= %s AND end_date <= %s)) ' \
                    'AND manager = %s ' \
                    'AND id != %s',
                (self.start_date, self.start_date,
                    self.end_date, self.end_date,
                    self.start_date, self.end_date,
                    self.manager.id, self.id))
        if cursor.fetchone():
            return False
        return True

    @staticmethod
    def default_start_date():
        res = Transaction().context.get('start_date')
        if not res:
            date = Pool().get('ir.date').today()
            res = date
        return res

    def get_good_rule_from_kind(self):
        for field_name, field_desc in self._fields.iteritems():
            if (hasattr(field_desc, 'model_name') and
                    field_desc.model_name == self.kind):
                return getattr(self, field_name)[0]

    def get_currency_digits(self, name):
        if self.manager:
            return self.manager.get_currency_digits(name)


class BusinessRuleRoot(CoopView, GetResult, Templated):
    'Business Rule Root'

    __name__ = 'ins_product.business_rule_root'

    config_kind = fields.Selection(CONFIG_KIND,
        'Conf. kind', required=True)
    generic_rule = fields.Many2One('ins_product.generic_business_rule',
        'Generic Rule', ondelete='CASCADE')
    rule = fields.Many2One('rule_engine', 'Rule Engine',
        depends=['config_kind'])

    @classmethod
    def __setup__(cls):
        super(BusinessRuleRoot, cls).__setup__()
        cls.template = copy.copy(cls.template)
        cls.template.model_name = cls.__name__

    def get_currency_digits(self, name):
        if self.generic_rule:
            return self.generic_rule.get_currency_digits(name)

    @staticmethod
    def default_config_kind():
        return 'simple'


class PricingData(CoopSQL, CoopView):
    'Pricing Data'

    __name__ = 'ins_product.pricing_data'

    calculator = fields.Many2One(
        'ins_product.pricing_calculator',
        'Calculator',
        ondelete='CASCADE')

    currency_digits = fields.Function(fields.Integer('Currency Digits'),
        'get_currency_digits')

    fixed_amount = fields.Numeric(
        'Amount',
        digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits', 'kind', 'config_kind'])

    config_kind = fields.Selection(CONFIG_KIND,
        'Conf. kind', required=True)

    rule = fields.Many2One('rule_engine', 'Rule Engine',
        depends=['config_kind', 'kind'])

    kind = fields.Selection(
        PRICING_LINE_KINDS,
        'Line kind',
        required=True)

    code = fields.Char('Code', required=True)

    the_tax = fields.Function(fields.Many2One(
            'coop_account.tax_desc',
            'Tax Descriptor'),
        'get_tax',
        'set_tax')

    the_fee = fields.Function(fields.Many2One(
            'coop_account.fee_desc',
            'Fee Descriptor'),
        'get_fee',
        'set_fee')

    summary = fields.Function(fields.Char('Value',
                    on_change_with=['fixed_amount', 'config_kind', 'rule',
                        'kind', 'the_tax', 'the_fee', 'code']),
        'get_summary')

    def get_tax(self, name):
        if not (self.kind == 'tax' and
                hasattr(self, 'code') and self.code):
            return
        tax = get_those_objects(
            'coop_account.tax_desc',
            [('code', '=', self.code)], 1)
        if tax:
            return tax[0].id

    @classmethod
    def set_tax(cls, calcs, name, value):
        if value:
            try:
                tax, = get_those_objects(
                    'coop_account.tax_desc',
                    [('id', '=', value)])
                code = tax.code
                cls.write(calcs, {'code': code})
            except ValueError:
                raise Exception(
                    'Could not found a Tax Desc with code %s' % value)

    def get_fee(self, name):
        if not (self.kind == 'fee' and
                hasattr(self, 'code') and self.code):
            return
        fee = get_those_objects(
            'coop_account.fee_desc',
            [('code', '=', self.code)], 1)
        if fee:
            return fee[0].id

    @classmethod
    def set_fee(cls, calcs, name, value):
        if value:
            try:
                fee, = get_those_objects(
                    'coop_account.fee_desc',
                    [('id', '=', value)])
                code = fee.code
                cls.write(calcs, {'code': code})
            except ValueError:
                raise Exception(
                    'Could not found a Fee Desc with code %s' % value)

    @staticmethod
    def default_kind():
        return 'base'

    @staticmethod
    def default_config_kind():
        return 'simple'

    def get_currency_digits(self, name):
        if self.calculator:
            return self.calculator.get_currency_digits(name)

    def calculate_tax(self, args):
        # No need to calculate here, it will be done at combination time
        return 0

    def calculate_fee(self, args):
        # No need to calculate here, it will be done at combination time
        return 0

    def calculate_value(self, args):
        result = 0
        errors = []
        kind = self.kind
        if self.kind == 'tax':
            amount = self.calculate_tax(args)
        elif self.kind == 'fee':
            amount = self.calculate_fee(args)
        elif self.config_kind == 'simple':
            amount = self.fixed_amount
        elif self.config_kind == 'rule' and self.rule:
            res, mess, errs = self.rule.compute(args)
            amount, errors = res, mess + errs
        code = self.code
        name = kind + ' - ' + code
        final_res = PricingResultLine(amount, name)
        final_res.update_details({(kind, code): amount})
        return final_res, errors

    def get_summary(self, name=None, with_label=False, at_date=None):
        res = ''
        if self.kind == 'tax' and self.the_tax:
            res = self.the_tax.rec_name
        elif self.kind == 'fee' and self.the_fee:
            res = self.the_fee.rec_name
        else:
            if self.config_kind == 'rule' and self.rule:
                res = self.rule.rec_name
            elif self.config_kind == 'simple':
                res = str(self.fixed_amount)
        return res

    def get_rec_name(self, name=None):
        return self.get_summary(name)

    def on_change_with_summary(self, name=None):
        return self.get_summary(name)


class PriceCalculator(CoopSQL, CoopView):
    'Price Calculator'

    __name__ = 'ins_product.pricing_calculator'

    currency_digits = fields.Function(fields.Integer('Currency Digits'),
        'get_currency_digits')

    data = fields.One2Many(
        'ins_product.pricing_data',
        'calculator',
        'Price Components'
        )

    key = fields.Selection(
        [('price', 'Subscriber Price'),
        ('sub_price', 'Sub Elem Price')],
        'Key')

    rule = fields.Many2One(
        'ins_product.pricing_rule',
        'Pricing Rule',
        ondelete='CASCADE')

    simple = fields.Boolean('Basic Combination')

    combine = fields.Many2One(
        'rule_engine',
        'Combining Rule',
        states={
            'invisible': Bool(Eval('simple')),
            'required': ~Bool(Eval('simple'))})

    def get_currency_digits(self, name):
        if hasattr(self, 'rule') and self.rule:
            return self.rule.get_currency_digits(name)

    def calculate_price(self, args):
        result = PricingResultLine()
        errors = []
        for data in self.data:
            res, errs = data.calculate_value(args)
            result += res
            errors += errs
        if not errors and not self.simple and \
                hasattr(self, 'combine') and self.combine:
            new_args = copy.copy(args)
            new_args['price_details'] = result.details
            final_details = {}
            for key in result.details.iterkeys():
                final_details[key] = 0
            new_args['final_details'] = final_details
            res, mess, errs = self.combine.compute(new_args)
            errors += mess + errs
            result = PricingResultLine(value=res)
            result.details = {}
            result.update_details(new_args['final_details'])
        elif not errs and self.simple:
            result.value = 0
            sorted = dict([(key, []) for key, _ in PRICING_LINE_KINDS])
            result.desc = []
            for key, value in result.details.iteritems():
                sorted[key[0]].append((key[1], value))
            for the_code, value in sorted['base']:
                result.value += value
            total_fee = 0
            for the_code, value in sorted['fee']:
                fee, = utils.get_those_objects(
                    'coop_account.fee_desc',
                    [('code', '=', the_code)], 1)
                fee_vers = fee.get_version_at_date(args['date'])
                amount = fee_vers.apply_fee(result.value)
                total_fee += amount
                result.details[('fee', the_code)] = amount
            result.value += total_fee
            total_tax = 0
            for the_code, value in sorted['tax']:
                tax, = utils.get_those_objects(
                    'coop_account.tax_desc',
                    [('code', '=', the_code)], 1)
                tax_vers = tax.get_version_at_date(args['date'])
                amount = tax_vers.apply_tax(result.value)
                total_tax += amount
                result.details[('tax', the_code)] = amount
            # result.value += total_tax
        result.create_descs_from_details()
        return result, errors

    def get_rec_name(self, name):
        return 'Price Calculator'

    @staticmethod
    def default_simple():
        return True


class PricingRule(CoopSQL, BusinessRuleRoot):
    'Pricing Rule'

    __name__ = 'ins_product.pricing_rule'

    price_kind = fields.Selection(
        [
            ('subscriber', 'Subscriber'),
            ('cov_element', 'Covered Elements')
        ],
        'Price based on',
        states={'required': Eval('config_kind') == 'rule'})

    calculators = fields.One2Many(
        'ins_product.pricing_calculator',
        'rule',
        'Calculators')

    price = fields.Function(fields.Many2One(
            'ins_product.pricing_calculator',
            'Price Calculator'),
        'get_calculator')

    sub_price = fields.Function(fields.Many2One(
            'ins_product.pricing_calculator',
            'Price Calculator'),
        'get_calculator')

    frequency = fields.Selection(
        PRICING_FREQUENCY,
        'Rate Frequency',
        required=True)

    basic_price = fields.Function(
        fields.Numeric(
            'Amount',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']),
        'get_basic_price',
        'set_basic_price')

    basic_tax = fields.Function(
        fields.Many2One(
            'coop_account.tax_desc',
            'Tax'),
        'get_basic_tax',
        'set_basic_tax')

    @staticmethod
    def default_config_kind():
        return 'simple'

    @classmethod
    def set_basic_price(cls, prices, name, value):
        if value:
            Calc = Pool().get('ins_product.pricing_calculator')
            Data = Pool().get('ins_product.pricing_data')
            for price in prices:
                if len(price.calculators) == 1:
                    the_calc = price.calculators[0]
                    Data.delete(
                        [data for data in the_calc.data
                            if data.kind == 'base'])
                else:
                    if len(price.calculators) > 1:
                        Calc.delete(price.calculators)
                    the_calc = Calc()
                    the_calc.key = 'price'
                    the_calc.data = []
                if the_calc.id:
                    the_calc.write([the_calc],
                        {'data': [(
                            'create', {
                                'fixed_amount': value,
                                'kind': 'base',
                                'code': 'PP'})]})
                else:
                    price.write([price], {
                        'calculators': [(
                            'create', {
                                'key': 'price',
                                'data': [(
                                    'create', {
                                        'fixed_amount': value,
                                        'code': 'PP',
                                        'kind': 'base'})]})]})

    @classmethod
    def set_basic_tax(cls, prices, name, value):
        if value:
            try:
                tax, = get_those_objects(
                    'coop_account.tax_desc',
                    [('id', '=', value)])
            except ValueError:
                raise Exception(
                    'Could not found a Tax Desc with code %s' % value)
            Calc = Pool().get('ins_product.pricing_calculator')
            Data = Pool().get('ins_product.pricing_data')
            for price in prices:
                if len(price.calculators) == 1:
                    the_calc = price.calculators[0]
                    Data.delete(
                        [data for data in the_calc.data
                            if data.kind == 'tax'])
                else:
                    if len(price.calculators) > 1:
                        Calc.delete(price.calculators)
                    the_calc = Calc()
                    the_calc.key = 'price'
                    the_calc.data = []
                if the_calc.id:
                    the_calc.write([the_calc],
                        {'data': [(
                            'create', {
                                'kind': 'tax',
                                'code': tax.code})]})
                else:
                    price.write([price], {
                        'calculators': [(
                            'create', {
                                'key': 'price',
                                'data': [(
                                    'create', {
                                        'code': tax.code,
                                        'kind': 'tax'})]})]})

    def get_basic_price(self, name):
        if not self.config_kind == 'simple':
            return 0
        calcs = [elem for elem in self.calculators if elem.key == 'price']
        if not calcs or len(calcs) > 1:
            return 0
        calc = calcs[0]
        datas = [data for data in calc.data if data.kind == 'base']
        if not datas or len(datas) > 1:
            return 0
        return datas[0].fixed_amount

    def get_basic_tax(self, name):
        if not self.config_kind == 'simple':
            return
        calcs = [elem for elem in self.calculators if elem.key == 'price']
        if not calcs or len(calcs) > 1:
            return
        calc = calcs[0]
        datas = [data for data in calc.data if data.kind == 'tax']
        if not datas or len(datas) > 1:
            return
        tax = get_those_objects(
            'coop_account.tax_desc',
            [('code', '=', datas[0].code)], 1)
        if tax:
            return tax[0].id

    def get_calculator(self, name):
        if hasattr(self, 'calculators') and self.calculators:
            for elem in self.calculators:
                if elem.key == name:
                    return WithAbstract.serialize_field(elem)
        return None

    def give_me_price(self, args):
        if self.price:
            result, errors = self.price.calculate_price(args)
        else:
            result, errors = (PricingResultLine(value=0), [])

        return result, errors

    def give_me_sub_elem_price(self, args):
        if self.sub_price:
            result, errors = self.sub_price.calculate_price(args)
        else:
            result, errors = (PricingResultLine(value=0), [])

        return result, errors

    def give_me_frequency(self, args):
        if hasattr(self, 'frequency') and self.frequency:
            return self.frequency
        return None

    def give_me_frequency_days(self, args):
        if not 'date' in args:
            return (None, ['A base date must be provided !'])
        date = args['date']
        return number_of_days_between(
            date,
            add_frequency(self.frequency, date))

    @classmethod
    def delete(cls, rules):
        def delete_link(inst, name):
            if hasattr(inst, name):
                val = getattr(inst, name)
                if val:
                    val.delete([val])

        for rule in rules:
            delete_link(rule, 'tax_mgr')
            delete_link(rule, 'sub_elem_taxes')

        super(PricingRule, cls).delete(rules)

    @staticmethod
    def default_price_kind():
        return 'subscriber'

    @staticmethod
    def default_frequency():
        return 'yearly'


class EligibilityRule(CoopSQL, BusinessRuleRoot):
    'Eligibility Rule'

    __name__ = 'ins_product.eligibility_rule'
    is_eligible = fields.Boolean('Is Eligible')
    sub_elem_config_kind = fields.Selection(CONFIG_KIND,
        'Sub Elem Conf. kind', required=True)
    sub_elem_rule = fields.Many2One('rule_engine', 'Sub Elem Rule Engine',
        depends=['config_kind'])
    is_sub_elem_eligible = fields.Boolean('Sub Elem Eligible')
    subscriber_classes = fields.Selection(
        SUBSCRIBER_CLASSES,
        'Can be subscribed',
        required=True)
    relation_kinds = fields.Many2Many('ins_product.eligibility_relation_kind',
        'eligibility_rule', 'relation_kind', 'Relations Authorized')

    def give_me_eligibility(self, args):
        # First of all, we look for a subscriber data in the args and update
        # the args dictionnary for sub values.
        try:
            update_args_with_subscriber(args)
        except ArgsDoNotMatchException:
            # If no Subscriber is found, automatic refusal
            return (EligibilityResultLine(
                False, ['Subscriber not defined in args']), [])

        # We define a match_table which will tell what data to look for
        # depending on the subscriber_eligibility attribute value.
        match_table = {
            'party.party': 'subscriber',
            'party.person': 'subscriber_person',
            'party.company': 'subscriber_company'}

        # if it does not match, refusal
        if not match_table[self.subscriber_classes] in args:
            return (EligibilityResultLine(
                False,
                ['Subscriber must be a %s'
                    % dict(SUBSCRIBER_CLASSES)[self.subscriber_classes]]),
                [])

        # Now we can call the rule if it exists :
        if hasattr(self, 'rule') and self.rule:
            res, mess, errs = self.rule.compute(args)
            return (EligibilityResultLine(eligible=res, details=mess), errs)

        # This is the most basic eligibility rule :
        if self.is_eligible:
            details = []
        else:
            details = ['Not eligible']
        return (
            EligibilityResultLine(eligible=self.is_eligible, details=details),
            [])

    def give_me_sub_elem_eligibility(self, args):
        if hasattr(self, 'sub_elem_rule') and self.sub_elem_rule:
            res, mess, errs = self.sub_elem_rule.compute(args)
            return (EligibilityResultLine(eligible=res, details=mess), errs)
        if self.is_sub_elem_eligible:
            details = []
        else:
            if 'sub_elem' in args and 'option' in args:
                details = ['%s not eligible for %s' %
                    (args['sub_elem'].get_name_for_info(),
                    args['option'].coverage.name)]
            else:
                details = ['Not eligible']
        return (
            EligibilityResultLine(
                eligible=self.is_sub_elem_eligible,
                details=details),
            [])

    @staticmethod
    def default_is_eligible():
        return True

    @staticmethod
    def default_is_sub_elem_eligible():
        return True

    @staticmethod
    def default_sub_elem_config_kind():
        return 'simple'

    @staticmethod
    def default_subscriber_classes():
        return 'party.person'


class EligibilityRelationKind(CoopSQL):
    'Define relation between eligibility rule and relation kind authorized'

    __name__ = 'ins_product.eligibility_relation_kind'

    eligibility_rule = fields.Many2One('ins_product.eligibility_rule',
        'Eligibility Rule', ondelete='CASCADE')
    relation_kind = fields.Many2One('party.party_relation_kind',
        'Relation Kind', ondelete='CASCADE')


class Benefit(CoopSQL, Offered):
    'Benefit'

    __name__ = 'ins_product.benefit'

    coverage = fields.Many2One('ins_product.coverage', 'Coverage',
        ondelete='CASCADE')
    benefit_mgr = One2ManyDomain('ins_product.business_rule_manager',
        'offered', 'Benefit Manager')
    reserve_mgr = One2ManyDomain('ins_product.business_rule_manager',
        'offered', 'Reserve Manager')

    def get_currency_digits(self, name):
        if self.coverage:
            return self.coverage.get_currency_digits(name)


class BenefitRule(CoopSQL, BusinessRuleRoot):
    'Benefit Rule'

    __name__ = 'ins_product.benefit_rule'


class ReserveRule(CoopSQL, BusinessRuleRoot):
    'Reserve Rule'

    __name__ = 'ins_product.reserve_rule'

    currency_digits = fields.Function(fields.Integer('Currency Digits'),
        'get_currency_digits')
    amount = fields.Numeric('Amount', digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits'])


class CoverageAmountRule(CoopSQL, BusinessRuleRoot):
    'Coverage Amount Rule'

    __name__ = 'ins_product.coverage_amount_rule'

    amounts = fields.Char('Amounts', help='Specify amounts separated by ;')

    def give_me_allowed_amounts(self, args):
        return [(elem, elem) for elem in self.amounts.split(';')]

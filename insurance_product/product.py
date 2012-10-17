#-*- coding:utf-8 -*-
import copy
import datetime
from trytond.model import fields as fields
from trytond.ir.model import SchemaElementMixin
from trytond.pool import Pool
from trytond.pyson import Eval, Bool, Or, Not
from trytond.transaction import Transaction
from trytond.rpc import RPC

from trytond.modules.coop_utils import model as model
from trytond.modules.coop_utils import business as business
from trytond.modules.coop_utils import utils as utils, date as date
from trytond.modules.coop_utils import string
from trytond.modules.insurance_product import PricingResultLine
from trytond.modules.insurance_product import EligibilityResultLine

try:
    import simplejson as json
except ImportError:
    import json

__all__ = ['Offered', 'Coverage', 'Product', 'ProductOptionsCoverage',
           'BusinessRuleManager', 'GenericBusinessRule', 'BusinessRuleRoot',
           'PricingRule', 'PriceCalculator', 'PricingData',
           'EligibilityRule', 'EligibilityRelationKind',
           'Benefit', 'BenefitRule', 'ReserveRule', 'CoverageAmountRule',
           'ProductDefinition',
           'CoopSchemaElement', 'SchemaElementRelation', 'DynamicDataManager']

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

DEF_CUR_DIG = 2


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


class Offered(model.CoopView, utils.GetResult, Templated):
    'Offered'

    __name__ = 'ins_product.offered'

    code = fields.Char('Code', size=10, required=True, select=1)
    name = fields.Char('Name', required=True, select=1)
    start_date = fields.Date('Start Date', required=True, select=1)
    end_date = fields.Date('End Date')
    description = fields.Text('Description')
    #All mgr var must be the same as the business rule class and ends with mgr
    pricing_mgr = model.One2ManyDomain('ins_product.business_rule_manager',
        'offered', 'Pricing Manager')
    eligibility_mgr = model.One2ManyDomain('ins_product.business_rule_manager',
        'offered', 'Eligibility Manager')
    summary = fields.Function(fields.Text('Summary'), 'get_summary')
    currency_digits = fields.Function(fields.Integer('Currency Digits'),
        'get_currency_digits')

    @classmethod
    def __setup__(cls):
        super(Offered, cls).__setup__()
        for field_name in (mgr for mgr in dir(cls) if mgr.endswith('_mgr')):
            cur_attr = copy.copy(getattr(cls, field_name))
            if not hasattr(cur_attr, 'context'):
                continue
            if cur_attr.context is None:
                cur_attr.context = {}
            cur_attr.context['start_date'] = Eval('start_date')
            cur_attr.context['currency_digits'] = Eval('currency_digits')
            if cur_attr.depends is None:
                cur_attr.depends = []
            utils.extend_inexisting(cur_attr.depends,
                ['start_date', 'currency_digits'])
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
            res = utils.today()
        return res

    def get_name_for_billing(self):
        return self.name

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


class Coverage(model.CoopSQL, Offered):
    'Coverage'

    __name__ = 'ins_product.coverage'

    insurer = fields.Many2One('party.insurer', 'Insurer')
    family = fields.Selection([('default', 'default')], 'Family',
        required=True)
    benefits = fields.One2Many('ins_product.benefit', 'coverage', 'Benefits',
        context={'start_date': Eval('start_date'),
                 'currency_digits': Eval('currency_digits')},
        states={'readonly': ~Bool(Eval('start_date'))},
        depends=['currency_digits'])
    currency = fields.Many2One('currency.currency', 'Currency', required=True)
    coverage_amount_mgr = model.One2ManyDomain(
        'ins_product.business_rule_manager',
        'offered', 'Coverage Amount Manager')

    @classmethod
    def delete(cls, entities):
        utils.delete_reference_backref(
            entities,
            'ins_product.business_rule_manager',
            'offered')
        super(Coverage, cls).delete(entities)

    @classmethod
    def __setup__(cls):
        super(Coverage, cls).__setup__()
        cls._sql_constraints += [
            ('code_uniq', 'UNIQUE(code)', 'The code must be unique!'),
        ]
        for field_name in (mgr for mgr in dir(cls) if mgr.endswith('_mgr')):
            cur_attr = copy.copy(getattr(cls, field_name))
            if not hasattr(cur_attr, 'context') or not isinstance(
                    cur_attr, fields.Field):
                continue
            if cur_attr.context is None:
                cur_attr.context = {}
            cur_attr.context['for_family'] = Eval('family')
            cur_attr = copy.copy(cur_attr)
            setattr(cls, field_name, cur_attr)

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
                    args)[0]:
                # Now we need to set a new argument before forwarding
                # the request to the manager, which is the covered
                # element it must work on.
                tmp_args = args
                tmp_args['for_covered'] = covered
                tmp_args['data'] = covered_data

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

    def give_me_family(self, args):
        return (Pool().get(self.family), [])

    def give_me_extension_field(self, args):
        return self.give_me_family(args)[0].get_extension_model()

    def give_me_covered_elements_at_date(self, args):
        contract = args['contract']
        date = args['date']
        res = []
        good_ext = self.give_me_extension_field(args)
        if not good_ext or not hasattr(contract, good_ext):
            return [], ['Extension not found']
        for covered in getattr(contract, good_ext)[0].covered_elements:
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
        return res, []

    def is_valid(self):
        if self.template_behaviour == 'remove':
            return False
        return True

    def get_rec_name(self, name):
        return '(%s) %s' % (self.code, self.name)

    def give_me_allowed_amounts(self, args):
        try:
            return self.get_result(
                'allowed_amounts',
                args,
                manager='coverage_amount')
        except utils.NonExistingManagerException:
            return [], []

    def give_me_coverage_amount_validity(self, args):
        try:
            return self.get_result(
                'coverage_amount_validity',
                args,
                manager='coverage_amount')
        except utils.NonExistingManagerException:
            return (True, []), []

    @classmethod
    def search_rec_name(cls, name, clause):
        if cls.search([('code',) + clause[1:]], limit=1):
            return [('code',) + clause[1:]]
        return [(cls._rec_name,) + clause[1:]]


class Product(model.CoopSQL, Offered):
    'Product'

    __name__ = 'ins_product.product'

    options = fields.Many2Many('ins_product.product-options-coverage',
        'product', 'coverage', 'Options',
        domain=[('currency', '=', Eval('currency'))],
        depends=['currency'])
    currency = fields.Many2One('currency.currency', 'Currency', required=True)
    contract_generator = fields.Many2One(
        'ir.sequence',
        'Contract Number Generator',
        context={'code': 'ins_product.product'},
        required=True,
        ondelete='RESTRICT')
    dynamic_data_manager = fields.One2Many(
        'ins_product.dynamic_data_manager',
        'product',
        'Dynamic Data Manager',
        size=1)

    @classmethod
    def __setup__(cls):
        super(Product, cls).__setup__()
        cls._sql_constraints += [
            ('code_uniq', 'UNIQUE(code)', 'The code must be unique!'),
        ]

    @classmethod
    def delete(cls, entities):
        utils.delete_reference_backref(
            entities,
            'ins_product.business_rule_manager',
            'offered')
        super(Product, cls).delete(entities)

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
            result.append(res)
            errors += errs
        return (result, errors)

    def give_me_frequency(self, args):
        if not 'date' in args:
            raise Exception('A date must be provided')
        try:
            return self.get_result('frequency', args, manager='pricing')
        except utils.NonExistingManagerException:
            pass
        for coverage in self.get_valid_options():
            try:
                return coverage.get_result(
                    'frequency', args, manager='pricing')
            except utils.NonExistingManagerException:
                pass
        return 'yearly', []

    @staticmethod
    def default_currency():
        return business.get_default_currency()

    def give_me_step(self, args):
        good_family = self.give_me_families(args)[0][0]
        return good_family.get_step_model(args['step_name']), []

    def give_me_new_contract_number(self, args):
        return self.contract_generator.get_id(self.contract_generator.id)

    def get_rec_name(self, name):
        return '(%s) %s' % (self.code, self.name)

    def give_me_dynamic_data_ids(self, args):
        if not(hasattr(self,
                'dynamic_data_manager') and self.dynamic_data_manager):
            return []
        return self.dynamic_data_manager[0].get_valid_schemas_ids(
            args['date'])

    def give_me_dynamic_data_init(self, args):
        if not(hasattr(self,
                'dynamic_data_manager') and self.dynamic_data_manager):
            return {}
        elems = self.dynamic_data_manager[0].get_valid_schemas(args['date'])
        res = {}
        for elem in elems:
            res[elem.technical_name] = elem.get_default_value(None)
        return res

    @classmethod
    def search_rec_name(cls, name, clause):
        if cls.search([('code',) + clause[1:]], limit=1):
            return [('code',) + clause[1:]]
        return [(cls._rec_name,) + clause[1:]]


class ProductOptionsCoverage(model.CoopSQL):
    'Define Product - Coverage relations'

    __name__ = 'ins_product.product-options-coverage'

    product = fields.Many2One('ins_product.product',
        'Product', select=1, required=True, ondelete='CASCADE')
    coverage = fields.Many2One('ins_product.coverage',
        'Coverage', select=1, required=True, ondelete='RESTRICT')


class BusinessRuleManager(model.CoopSQL, model.CoopView,
        utils.GetResult, Templated):
    'Business Rule Manager'

    __name__ = 'ins_product.business_rule_manager'

    offered = fields.Reference('Offered', selection='get_offered_models')
    business_rules = fields.One2Many('ins_product.generic_business_rule',
        'manager', 'Business Rules', on_change=['business_rules'])

    @classmethod
    def __setup__(cls):
        super(BusinessRuleManager, cls).__setup__()
        cls.template = copy.copy(cls.template)
        cls.template.model_name = cls.__name__
        cls.__rpc__.update({'get_offered_models': RPC()})

    @staticmethod
    def get_offered_models():
        return utils.get_descendents(Offered)

    def on_change_business_rules(self):
        res = {'business_rules': {}}
        res['business_rules'].setdefault('update', [])
        for business_rule1 in self.business_rules:
            #the idea is to always set the end_date
            #to the according next start_date
            for business_rule2 in self.business_rules:
                if (business_rule1 != business_rule2
                    and business_rule2.start_date
                    and business_rule1.start_date
                    and business_rule2.start_date > business_rule1.start_date
                    and (not business_rule1.end_date
                        or business_rule1.end_date >= business_rule2.start_date
                        )
                    ):
                    end_date = (business_rule2.start_date
                        - datetime.timedelta(days=1))
                    res['business_rules']['update'].append({
                        'id': business_rule1.id,
                        'end_date': end_date})

            #if we change the start_date to a date after the end_date,
            #we reinitialize the end_date
            if (business_rule1.end_date
                and business_rule1.start_date
                and business_rule1.end_date < business_rule1.start_date):
                res['business_rules']['update'].append(
                    {
                        'id': business_rule1.id,
                        'end_date': None
                    })
        return res

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

    def get_rec_name(self, name):
        res = ''
        if self.business_rules and len(self.business_rules) > 0:
            res = self.business_rules[0].kind
        if res != '':
            res += ' '
        res += '(%s)' % self.id
        return res

    def get_offered(self):
        return self.offered

#    @staticmethod
#    def default_business_rules():
#        return utils.create_inst_with_default_val(BusinessRuleManager,
#            'business_rules')


class GenericBusinessRule(model.CoopSQL, model.CoopView):
    'Generic Business Rule'

    __name__ = 'ins_product.generic_business_rule'

    kind = fields.Selection('get_kind', 'Kind',
        required=True, on_change=['kind'])  # , states={'readonly': True})
    manager = fields.Many2One('ins_product.business_rule_manager', 'Manager',
        ondelete='CASCADE')
    start_date = fields.Date('From Date', required=True,
        depends=['is_current'])
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
        for field_name, field in self._fields.iteritems():
            if not (hasattr(field, 'model_name')
                and getattr(field, 'model_name').endswith('_rule')
                and (not getattr(self, field_name)
                    or len(getattr(self, field_name)) == 0)):
                continue
            if field.model_name != self.kind:
                continue
            res[field_name] = utils.create_inst_with_default_val(
                self.__class__, field_name, action='add')
        return res

    @staticmethod
    def get_kind():
        return string.get_descendents_name(BusinessRuleRoot)

    def get_is_current(self, name):
        #first we need the model for the manager (depends on the module used
        if not hasattr(self.__class__, 'manager'):
            return False
        manager_attr = getattr(self.__class__, 'manager')
        if not hasattr(manager_attr, 'model_name'):
            return False
        BRM = Pool().get(manager_attr.model_name)
        date = utils.today()
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
            date = utils.today()
            res = date
        return res

    def get_good_rule_from_kind(self):
        for field_name, field_desc in self._fields.iteritems():
            if (hasattr(field_desc, 'model_name') and
                    field_desc.model_name == self.kind):
                return getattr(self, field_name)[0]

    def get_offered(self):
        return self.manager.get_offered()


class BusinessRuleRoot(model.CoopView, utils.GetResult, Templated):
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

    @staticmethod
    def default_config_kind():
        return 'simple'

    def get_offered(self):
        return self.generic_rule.get_offered()


class PricingData(model.CoopSQL, model.CoopView):
    'Pricing Data'

    __name__ = 'ins_product.pricing_data'

    calculator = fields.Many2One(
        'ins_product.pricing_calculator',
        'Calculator',
        ondelete='CASCADE')

    fixed_amount = fields.Numeric(
        'Amount',
        digits=(16, Eval('context', {}).get('currency_digits', DEF_CUR_DIG)),
        depends=['kind', 'config_kind'])

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
        tax = utils.get_those_objects(
            'coop_account.tax_desc',
            [('code', '=', self.code)], 1)
        if tax:
            return tax[0].id

    @classmethod
    def set_tax(cls, calcs, name, value):
        if value:
            try:
                tax, = utils.get_those_objects(
                    'coop_account.tax_desc',
                    [('id', '=', value)])
                code = tax.code
                cls.write(calcs, {'code': code})
            except ValueError:
                raise Exception(
                    'Could not found the required Tax Desc')

    def get_fee(self, name):
        if not (self.kind == 'fee' and
                hasattr(self, 'code') and self.code):
            return
        fee = utils.get_those_objects(
            'coop_account.fee_desc',
            [('code', '=', self.code)], 1)
        if fee:
            return fee[0].id

    @classmethod
    def set_fee(cls, calcs, name, value):
        if value:
            try:
                fee, = utils.get_those_objects(
                    'coop_account.fee_desc',
                    [('id', '=', value)])
                code = fee.code
                cls.write(calcs, {'code': code})
            except ValueError:
                raise Exception(
                    'Could not found the required Fee desc')

    @classmethod
    def create(cls, values):
        values = values.copy()
        if 'the_tax' in values:
            try:
                tax, = utils.get_those_objects(
                    'coop_account.tax_desc',
                    [('id', '=', values['the_tax'])])
                values['code'] = tax.code
            except ValueError:
                raise Exception(
                    'Could not found the required Tax Desc')
        elif 'the_fee' in values:
            try:
                fee, = utils.get_those_objects(
                    'coop_account.fee_desc',
                    [('id', '=', values['the_fee'])])
                values['code'] = fee.code
            except ValueError:
                raise Exception(
                    'Could not found the required Fee desc')
        super(PricingData, cls).create(values)

    @staticmethod
    def default_kind():
        return 'base'

    @staticmethod
    def default_config_kind():
        return 'simple'

    def calculate_tax(self, args):
        # No need to calculate here, it will be done at combination time
        return 0

    def calculate_fee(self, args):
        # No need to calculate here, it will be done at combination time
        return 0

    def calculate_value(self, args):
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

    @classmethod
    def get_summary(cls, pricings, name=None, with_label=False, at_date=None,
                    lang=None):
        res = {}
        for pricing in pricings:
            res[pricing.id] = ''
            if pricing.kind == 'tax' and pricing.the_tax:
                res[pricing.id] = pricing.the_tax.rec_name
            elif pricing.kind == 'fee' and pricing.the_fee:
                res[pricing.id] = pricing.the_fee.rec_name
            else:
                if pricing.config_kind == 'rule' and pricing.rule:
                    res[pricing.id] = pricing.rule.rec_name
                elif pricing.config_kind == 'simple':
                    res[pricing.id] = str(pricing.fixed_amount)
        return res

    def get_rec_name(self, name=None):
        return self.get_summary([self])[self.id]

    def on_change_with_summary(self, name=None):
        return self.get_summary([self])[self.id]


class PriceCalculator(model.CoopSQL, model.CoopView):
    'Price Calculator'

    __name__ = 'ins_product.pricing_calculator'

    data = fields.One2Many(
        'ins_product.pricing_data',
        'calculator',
        'Price Components',
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

#Not working for the moment
#    @staticmethod
#    def default_data():
#        return utils.create_inst_with_default_val(
#            Pool().get('ins_product.pricing_calculator'), 'data')


class PricingRule(model.CoopSQL, BusinessRuleRoot):
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
            digits=(16,
                Eval('context', {}).get('currency_digits', DEF_CUR_DIG)),
            ),
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
                tax, = utils.get_those_objects(
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
        tax = utils.get_those_objects(
            'coop_account.tax_desc',
            [('code', '=', datas[0].code)], 1)
        if tax:
            return tax[0].id

    def get_calculator(self, name):
        if hasattr(self, 'calculators') and self.calculators:
            for elem in self.calculators:
                if elem.key == name:
                    return utils.WithAbstract.serialize_field(elem)
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
        the_date = args['date']
        return date.number_of_days_between(
            the_date,
            utils.add_frequency(self.frequency, the_date))

    @staticmethod
    def default_price_kind():
        return 'subscriber'

    @staticmethod
    def default_frequency():
        return 'yearly'


class EligibilityRule(model.CoopSQL, BusinessRuleRoot):
    'Eligibility Rule'

    __name__ = 'ins_product.eligibility_rule'
    sub_elem_config_kind = fields.Selection(CONFIG_KIND,
        'Sub Elem Conf. kind', required=True)
    sub_elem_rule = fields.Many2One('rule_engine', 'Sub Elem Rule Engine',
        depends=['config_kind'])
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
            business.update_args_with_subscriber(args)
        except business.ArgsDoNotMatchException:
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

        # Default eligibility is "True" :
        return (
            EligibilityResultLine(eligible=True),
            [])

    def give_me_sub_elem_eligibility(self, args):
        if hasattr(self, 'sub_elem_rule') and self.sub_elem_rule:
            res, mess, errs = self.sub_elem_rule.compute(args)
            return (EligibilityResultLine(eligible=res, details=mess), errs)
        return (EligibilityResultLine(True), [])

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


class EligibilityRelationKind(model.CoopSQL):
    'Define relation between eligibility rule and relation kind authorized'

    __name__ = 'ins_product.eligibility_relation_kind'

    eligibility_rule = fields.Many2One('ins_product.eligibility_rule',
        'Eligibility Rule', ondelete='CASCADE')
    relation_kind = fields.Many2One('party.party_relation_kind',
        'Relation Kind', ondelete='CASCADE')


class Benefit(model.CoopSQL, Offered):
    'Benefit'

    __name__ = 'ins_product.benefit'

    coverage = fields.Many2One('ins_product.coverage', 'Coverage',
        ondelete='CASCADE')
    benefit_mgr = model.One2ManyDomain('ins_product.business_rule_manager',
        'offered', 'Benefit Manager')
    reserve_mgr = model.One2ManyDomain('ins_product.business_rule_manager',
        'offered', 'Reserve Manager')
    kind = fields.Selection(
        [
            ('capital', 'Capital'),
            ('annuity', 'Annuity')
        ],
        'Kind', required=True)

    @classmethod
    def delete(cls, entities):
        utils.delete_reference_backref(
            entities,
            'ins_product.business_rule_manager',
            'offered')
        super(Benefit, cls).delete(entities)

    @staticmethod
    def default_kind():
        return 'capital'


class BenefitRule(model.CoopSQL, BusinessRuleRoot):
    'Benefit Rule'

    __name__ = 'ins_product.benefit_rule'

    kind = fields.Selection(
        [
            ('amount', 'Amount'),
            ('cov_amount', 'Coverage Amount')
        ],
        'Kind')

    amount = fields.Numeric(
        'Amount',
        digits=(16, Eval('context', {}).get('currency_digits', DEF_CUR_DIG)),
        states={'invisible': Eval('kind') != 'amount'},
        )

    coef_coverage_amount = fields.Numeric(
        'Multiplier',
        states={'invisible': Eval('kind') != 'cov_amount'},
        help='Add a multiplier to apply to the coverage amount',
        )

    @staticmethod
    def default_coef_coverage_amount():
        return 1

    @staticmethod
    def default_kind():
        return 'cov_amount'


class ReserveRule(model.CoopSQL, BusinessRuleRoot):
    'Reserve Rule'

    __name__ = 'ins_product.reserve_rule'

    amount = fields.Numeric('Amount',
        digits=(16, Eval('context', {}).get('currency_digits', DEF_CUR_DIG)),
        )


class CoverageAmountRule(model.CoopSQL, BusinessRuleRoot):
    'Coverage Amount Rule'

    __name__ = 'ins_product.coverage_amount_rule'

    kind = fields.Selection(
        [
            ('amount', 'Amount'),
            ('cal_list', 'Calculated List')
        ],
        'Kind')
    amounts = fields.Char('Amounts', help='Specify amounts separated by ;',
        states={'invisible': Eval('kind') != 'amount'},)
    amount_start = fields.Numeric('From',
        digits=(16, Eval('context', {}).get('currency_digits', DEF_CUR_DIG)),
        states={'invisible': Eval('kind') != 'cal_list'})
    amount_end = fields.Numeric('To',
        digits=(16, Eval('context', {}).get('currency_digits', DEF_CUR_DIG)),
        states={'invisible': Eval('kind') != 'cal_list'})
    amount_step = fields.Numeric('Step',
        digits=(16, Eval('context', {}).get('currency_digits', DEF_CUR_DIG)),
        states={'invisible': Eval('kind') != 'cal_list'})

    @classmethod
    def __setup__(cls):
        super(CoverageAmountRule, cls).__setup__()
        cls._error_messages.update({
                'amounts_float': 'Amounts need to be floats !',
                })

    def give_me_allowed_amounts(self, args):
        if self.config_kind == 'simple':
            if self.kind == 'amount' and self.amounts:
                res = map(float, self.amounts.split(';'))
                return res, []
            elif self.kind == 'cal_list' and self.amount_end:
                start = self.amount_start if self.amount_start else 0
                step = self.amount_step if self.amount_step else 1
                res = range(start, self.amount_end + 1, step)
                return res, []
        elif self.config_kind == 'rule' and self.rule:
            res, mess, errs = self.rule.compute(args)
            if res:
                res = map(float, res.split(';'))
            return res, mess + errs

    def give_me_coverage_amount_validity(self, args):
        if not('data' in args and hasattr(args['data'], 'coverage_amount')
                and args['data'].coverage_amount):
            return (False, []), ['Coverage amount not found']
        amount = args['data'].coverage_amount
        if hasattr(self, 'amounts') and self.amounts:
            if not amount in self.give_me_allowed_amounts(args)[0]:
                errs = ['Amount %.2f not allowed on coverage %s' % (
                    amount,
                    args['data'].for_coverage.name)]
                return (False, errs), []
        return (True, []), []

    def pre_validate(self):
        if not hasattr(self, 'amounts'):
            return
        if self.config_kind == 'simple':
            try:
                map(float, self.amounts.split(';'))
            except ValueError:
                self.raise_user_error('amounts_float')


class ProductDefinition(model.CoopView):
    'Product Definition'

    # This class is the base of Product Definitions. It defines number of
    # methods which will be used to define a business family behaviour in
    # the application

    def get_extension_model(self):
        raise NotImplementedError


class CoopSchemaElement(SchemaElementMixin, model.CoopSQL, model.CoopView):
    'Dynamic Data Definition'

    __name__ = 'ins_product.schema_element'

    manager = fields.Many2One(
        'ins_product.dynamic_data_manager',
        'Manager',
        ondelete='CASCADE')
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    with_default_value = fields.Boolean('Default Value')
    default_value_boolean = fields.Function(fields.Boolean(
        'Default Value'),
        'get_default_value',
        'set_default_value')
    default_value_char = fields.Function(fields.Char(
        'Default Value'),
        'get_default_value',
        'set_default_value')
    default_value_selection = fields.Function(fields.Char(
        'Default Value'),
        'get_default_value',
        'set_default_value')
    default_value = fields.Char('Default Value')
    is_shared = fields.Function(fields.Boolean('Shared'), 'get_is_shared')

    @classmethod
    def __setup__(cls):
        super(CoopSchemaElement, cls).__setup__()

        def update_field(field_name, field):
            if not hasattr(field, 'states'):
                field.states = {}
            field.states['invisible'] = Or(
                Eval('type_') != field_name[14:],
                ~Bool(Eval('with_default_value')))
            if field_name[14:] == 'selection':
                field.states['required'] = Not(field.states['invisible'])

        map(lambda x: update_field(x[0], x[1]),
            [(elem, getattr(cls, elem)) for elem in dir(cls) if
                elem.startswith('default_value_')])

    @staticmethod
    def default_start_date():
        return utils.today()

    def get_is_shared(self, name):
        return self.id and not self.manager is None

    def get_default_value(self, name):
        if name is None:
            name_type = self.type_
        else:
            name_type = name[14:]
        if name_type == 'boolean':
            return self.default_value == 'True'
        if name_type == 'char' or name_type == 'selection':
            return self.default_value

    @classmethod
    def set_default_value(cls, schemas, name, value):
        name_type = name[14:]
        if name_type == 'boolean':
            if value:
                cls.write(schemas, {'default_value': 'True'})
            else:
                cls.write(schemas, {'default_value': 'False'})
        elif name_type == 'char' or name_type == 'selection':
            cls.write(schemas, {'default_value': value})

    @classmethod
    def search(cls, domain, offset=0, limit=None, order=None, count=False,
            query_string=False):
        # Important : if you do not check (and set below) relation_selection,
        # There is a risk of infinite recursion if your code needs to do a
        # search (might only be a O2M / M2M)
        if not('relation_selection' in Transaction().context) and \
                'for_product' in Transaction().context and \
                'at_date' in Transaction().context:
            for_product = Transaction().context['for_product']
            at_date = Transaction().context['at_date']
            if for_product and at_date:
                the_product, = Pool().get('ins_product.product').search(
                    [('id', '=', Transaction().context['for_product'])])
                with Transaction().set_context({'relation_selection': True}):
                    good_schemas = the_product.get_result(
                        'dynamic_data_ids',
                        {'date': Transaction().context['at_date']})
                domain.append(('id', 'in', good_schemas[0]))
        return super(CoopSchemaElement, cls).search(domain, offset=offset,
                limit=limit, order=order, count=count,
                query_string=query_string)

    @classmethod
    def describe_keys(cls, key_ids):
        keys = []
        for key in cls.browse(key_ids):
            with Transaction().set_context(language='fr_FR'):
                english_key = cls(key.id)
                choices = dict(json.loads(english_key.choices or '[]'))
            choices.update(dict(json.loads(key.choices or '[]')))
            new_key = {
                'name': key.name,
                'technical_name': key.technical_name,
                'type_': key.type_,
                'choices': choices.items(),
            }
            keys.append(new_key)
        return keys


class SchemaElementRelation(model.CoopSQL):
    'Relation between schema element and dynamic data manager'

    __name__ = 'ins_product.schema_element_relation'

    the_manager = fields.Many2One('ins_product.dynamic_data_manager',
        'Manager', select=1, required=True, ondelete='CASCADE')
    schema_element = fields.Many2One('ins_product.schema_element',
        'Schema Element', select=1, required=True, ondelete='RESTRICT')


class DynamicDataManager(model.CoopSQL, model.CoopView):
    'Dynamic Data Manager'

    __name__ = 'ins_product.dynamic_data_manager'

    product = fields.Many2One(
        'ins_product.product',
        'Product',
        ondelete='CASCADE')

    specific_dynamic = fields.One2Many(
        'ins_product.schema_element',
        'manager',
        'Specific Dynamic Data')
    shared_dynamic = fields.Many2Many(
        'ins_product.schema_element_relation',
        'the_manager',
        'schema_element',
        'Shared Dynamic Data',
        domain=[('manager', '=', None)])

    def get_valid_schemas_ids(self, date):
        res = []
        for elem in self.specific_dynamic:
            res.append(elem.id)
        for elem in self.shared_dynamic:
            res.append(elem.id)
        return res

    def get_valid_schemas(self, date):
        res = []
        for elem in self.specific_dynamic:
            res.append(elem)
        for elem in self.shared_dynamic:
            res.append(elem)
        return res

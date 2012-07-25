#-*- coding:utf-8 -*-
import copy
import datetime

from trytond.model import fields as fields
from trytond.pool import Pool
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.rpc import RPC

from trytond.modules.coop_utils import utils, CoopView, CoopSQL, GetResult
from trytond.modules.coop_utils import get_data_from_dict
from trytond.modules.coop_utils import convert_ref_to_obj, PricingResultLine

__all__ = ['Offered', 'Coverage', 'Product', 'ProductOptionsCoverage',
           'BusinessRuleManager', 'GenericBusinessRule', 'BusinessRuleRoot',
           'PricingRule', 'EligibilityRule', 'PricingContext_Contract']


class Offered(CoopView, GetResult):
    'Offered'

    __name__ = 'ins_product.offered'

    code = fields.Char('Code', size=10, required=True, select=1)
    name = fields.Char('Name', required=True, select=1)
    start_date = fields.Date('Start Date', required=True, select=1)
    end_date = fields.Date('End Date')
    template = fields.Many2One(None, 'Template',
        domain=[('id', '!=', Eval('id'))],
        depends=['id'])
    #all mgr are Many2One because they all have the same backref var and though
    #it's not possible for the moment to have a O2M(1)
    #
    #All mgr var must be the same as the business rule class and ends with mgr
    pricing_mgr = fields.Many2One('ins_product.business_rule_manager',
        'Pricing Manager')
    eligibility_mgr = fields.Many2One('ins_product.business_rule_manager',
        'Eligibility Manager')

    @classmethod
    def __setup__(cls):
        super(Offered, cls).__setup__()
        for field_name in (mgr for mgr in dir(cls) if mgr.endswith('mgr')):
            cur_attr = copy.copy(getattr(cls, field_name))
            if not hasattr(cur_attr, 'context'):
                continue
            if cur_attr.context is None:
                cur_attr.context = {}
            cur_attr.context['mgr'] = field_name
            if not hasattr(cur_attr, 'model_name'):
                continue
            cur_attr.domain = [('business_rules.kind', '=',
                    '%s.%s_rule' %
                        (utils.get_module_name(cls),
                        field_name.split('_mgr')[0]))]
            setattr(cls, field_name, copy.copy(cur_attr))
        cls.template = copy.copy(cls.template)
        cls.template.model_name = cls.__name__


class Coverage(CoopSQL, Offered):
    'Coverage'

    __name__ = 'ins_product.coverage'

    insurer = fields.Many2One('party.insurer', 'Insurer')

    def give_me_price(self, args):
        # This method is one of the core of the pricing system. It asks for the
        # price for the self depending on the contrat that is given as an
        # argument.
        data_dict, errs = get_data_from_dict(['contract', 'date'], args)
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
                        _res.name = 'Base Price'
                res += _res
            # We always append the errors (if any).
            errs += _errs

            # Now it is time to price the covered elements of the contract.
            # Note that they might have a role in the Base Price computation,
            # depending on the algorithm that is used.
            #
            # What we compute now is the part of the price that is associated
            # to each of the covered elements.
            #
            # For now, the extension is hardcoded as a first step. It should be
            # made more generic in the future.
            if hasattr(contract, 'extension_life'):
                # First of all we go through the list of covered elements on
                # the contract's extension which matches self
                for covered in contract.extension_life.covered_elements:
                    # Then we must check that the current covered element is
                    # covered by self.
                    for covered_data in covered.covered_data:
                        for_coverage = convert_ref_to_obj(
                            covered_data.for_coverage)
                        if not for_coverage.code == self.code:
                            continue

                        # And that this coverage is effective at the requested
                        # computation date.
                        if not (date >= covered_data.start_date and
                                (not hasattr(covered_data, 'end_date') or
                                    covered_data.end_date is None or
                                    covered_data.end_date < date)):
                            break

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
                            _res.name = convert_ref_to_obj(
                                covered.product_specific).person.name
                            if covered_data.id:
                                _res.on_object = '%s,%s' % (
                                    covered_data.__name__,
                                    covered_data.id)
                            res += _res
                            errs += _errs
                        break
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
        if self.pricing_mgr:
            for rule in self.pricing_mgr.business_rules:
                res.add(rule.start_date)
        return res


class Product(CoopSQL, Offered):
    'Product'

    __name__ = 'ins_product.product'

    options = fields.Many2Many('ins_product.product-options-coverage',
        'product', 'coverage', 'Options')

    @classmethod
    def __setup__(cls):
        super(Product, cls).__setup__()

    def get_sub_elem_data(self):
        # This method is used by the get_result method to know where to look
        # for sub-elements to parse and what fields can be used for key
        # matching
        #
        # Here it states that Product objects have a list of 'options' which
        # implements the GetResult class, and on which we might use 'code' or
        # 'name' as keys.
        return ('options', ['code', 'name'])

    def give_me_options_price(self, args):
        # Getting the options price is easy : just loop and append the results
        errs = []
        res = PricingResultLine(name='Options')
        for option in self.options:
            _res, _errs = option.get_result('price', args)
            if not _res is None:
                res += _res
            errs += _errs
        return (res, errs)

    def give_me_product_price(self, args):
        # There is a pricing manager on the products so we can just forward the
        # request.
        res = self.get_result('price', args, manager='pricing')
        if not res[0]:
            res = (PricingResultLine(), res[1])
        data_dict, errs = get_data_from_dict(['contract'], args)
        if errs:
            # No contract means no price.
            return (None, errs)
        contract = data_dict['contract']
        res[0].name = 'Product Base Price'
        if contract.id:
            res[0].on_object = '%s,%s' % (contract.__name__, contract.id)
        try:
            res[1].remove('Business Manager pricing does not exist on %s'
                % self.name)
        except ValueError:
            pass
        return res

    def give_me_total_price(self, args):
        # Total price is the sum of Options price and Product price
        (p_price, errs_product) = self.give_me_product_price(args)
        (o_price, errs_options) = self.give_me_options_price(args)
        total_price = p_price + o_price
        total_price.name = 'Total Price'
        return (total_price, errs_product + errs_options)


class ProductOptionsCoverage(CoopSQL):
    'Define Product - Coverage relations'

    __name__ = 'ins_product.product-options-coverage'

    product = fields.Many2One('ins_product.product',
                              'Product',
                              select=1,
                              required=True)
    coverage = fields.Many2One('ins_product.coverage',
                               'Coverage',
                               select=1,
                               required=True)


class BusinessRuleManager(CoopSQL, CoopView, GetResult):
    'Business Rule Manager'

    __name__ = 'ins_product.business_rule_manager'

    belongs_to = fields.Function(
        fields.Reference('belongs_to', selection='get_offered_models'),
        'get_belongs_to')
    template = fields.Many2One(None, 'Template',
        domain=[('id', '!=', Eval('id'))],
        depends=['id'])
    business_rules = fields.One2Many('ins_product.generic_business_rule',
        'manager', 'Business Rules', on_change=['business_rules'],
        context={'start_date': Eval('start_date')})

    @classmethod
    def __setup__(cls):
        super(BusinessRuleManager, cls).__setup__()
        cls.template = copy.copy(cls.template)
        cls.template.model_name = cls.__name__
        cls.__rpc__.update({'get_offered_models': RPC()})

    @staticmethod
    def get_offered_models():
        return utils.get_descendents(Offered)

    def get_belongs_to(self, name):
        for offered_model, _offered_name in self.get_offered_models():
            Offered = Pool().get(offered_model)
            field_name = Transaction().context.get('mgr')
            if hasattr(Offered, 'search'):
                offered = Offered.search([(field_name, '=', self.id)])
                if len(offered) > 0:
                    return '%s, %s' % (offered_model, offered[0].id)
        return ''

    def on_change_business_rules(self):
        res = {'business_rules': {}}
        res['business_rules'].setdefault('update', [])
        for business_rule1 in self.business_rules:
            #the idea is to always set the end_date
            #to the according next start_date
            for business_rule2 in self.business_rules:
                if (business_rule1 != business_rule2 and
                    business_rule2['start_date'] is not None
                    and business_rule1['start_date'] is not None and
                    business_rule2['start_date'] > business_rule1['start_date']
                    and (business_rule1['end_date'] is None or
                         business_rule1['end_date'] >=
                         business_rule2['start_date'])):
                    end_date = (business_rule2['start_date']
                               - datetime.timedelta(days=1))
                    res['business_rules']['update'].append({
                        'id': business_rule1.id,
                        'end_date': end_date})

            #if we change the start_date to a date after the end_date,
            #we reinitialize the end_date
            if (business_rule1['end_date'] is not None
                and business_rule1['start_date'] is not None
                and business_rule1['end_date'] < business_rule1['start_date']):
                res['business_rules']['update'].append({
                        'id': business_rule1.id,
                        'end_date': None})
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
            for business_rule in self.business_rules:
                if business_rule.start_date <= the_date:
                    if not business_rule.end_date or \
                            business_rule.end_date > the_date:
                        return business_rule
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
    eligibilty_rule = fields.One2Many('ins_product.eligibility_rule',
        'generic_rule', 'Eligibility Rule', size=1)

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
            if (hasattr(field, 'model_name')
                and getattr(field, 'model_name').endswith('_rule')
                and (not getattr(self, field_name)
                     or len(getattr(self, field_name) == 0))):

                if field.model_name == self.kind:
                    res[field_name] = {}
                    res[field_name]['add'] = [{}]
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
        return self == BRM.get_good_rule_at_date(self.manager,
                {'date': datetime.date.today()})

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
        return Transaction().context.get('start_date')

    def get_good_rule_from_kind(self):
        for field_name, field_desc in self._fields.iteritems():
            if (hasattr(field_desc, 'model_name') and
                    field_desc.model_name == self.kind):
                return getattr(self, field_name)[0]


class BusinessRuleRoot(CoopView, GetResult):
    'Business Rule Root'

    __name__ = 'ins_product.business_rule_root'

    generic_rule = fields.Many2One('ins_product.generic_business_rule',
        'Generic Rule', ondelete='CASCADE')
    template = fields.Many2One(None, 'Template',
        domain=[('id', '!=', Eval('id'))],
        depends=['id'])

    @classmethod
    def __setup__(cls):
        super(BusinessRuleRoot, cls).__setup__()
        cls.template = copy.copy(cls.template)
        cls.template.model_name = cls.__name__


class PricingRule(CoopSQL, BusinessRuleRoot):
    'Pricing Rule'

    __name__ = 'ins_product.pricing_rule'

    price_rule = fields.Many2One(
        'rule_engine',
        'Rule for Price Calculation')

    price = fields.Numeric('Amount', digits=(16, 2), required=True)

    per_sub_elem_price = fields.Numeric(
        'Amount per Covered Element',
        digits=(16, 2))

    def give_me_price(self, args):
        if hasattr(self, 'price_rule') and self.price_rule:
            res = self.price_rule.compute(args)
            return (PricingResultLine(value=res), [])

        # This is the most basic pricing rule : just return the price
        return (PricingResultLine(value=self.price), [])

    def give_me_sub_elem_price(self, args):
        # This will be called for each covered element of the contract
        return (PricingResultLine(value=self.per_sub_elem_price), [])


class EligibilityRule(CoopSQL, BusinessRuleRoot):
    'Eligibility Rule'

    __name__ = 'ins_product.eligibility_rule'

    is_eligible = fields.Boolean('Is Eligible')


class PricingContext_Contract(CoopView):
    '''
        Context functions for pricing rules on contracts.
    '''
    __name__ = 'ins_product.rule_sets.pricing.contract'

    @classmethod
    def get_subscriber_name(cls, args):
        name = args['contract'].subscriber.name
        print name
        return name

#-*- coding:utf-8 -*-
import copy
import datetime

from trytond.model import fields as fields
from trytond.pool import Pool
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.rpc import RPC

from trytond.modules.coop_utils import utils, CoopView, CoopSQL

__all__ = ['Offered', 'Coverage', 'Product', 'ProductOptionsCoverage',
           'BusinessRuleManager', 'GenericBusinessRule', 'BusinessRuleRoot',
           'PricingRule', 'EligibilityRule']


class Offered(CoopView):
    'Offered'

    __name__ = 'ins_product.offered'

    code = fields.Char('Code', size=10, required=True, select=1)
    name = fields.Char('Name', required=True, select=1)
    start_date = fields.Date('Start Date', required=True, select=1)
    end_date = fields.Date('End Date')
    template = fields.Many2One(None, 'Template',
        domain=[('id', '!=', Eval('id'))])
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


class Product(CoopSQL, Offered):
    'Product'

    __name__ = 'ins_product.product'

    options = fields.Many2Many('ins_product.product-options-coverage',
        'product', 'coverage', 'Options')

    @classmethod
    def __setup__(cls):
        super(Product, cls).__setup__()


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


class BusinessRuleManager(CoopSQL, CoopView):
    'Business Rule Manager'

    __name__ = 'ins_product.business_rule_manager'

    belongs_to = fields.Function(
        fields.Reference('belongs_to', selection='get_offered_models'),
        'get_belongs_to')
    template = fields.Many2One(None, 'Template',
        domain=[('id', '!=', Eval('id'))])
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
            for busines_rule in self.business_rules:
                if busines_rule.start_date <= the_date:
                    return busines_rule
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
    manager = fields.Many2One('ins_product.business_rule_manager', 'Manager')
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


class BusinessRuleRoot(CoopView):
    'Business Rule Root'

    __name__ = 'ins_product.business_rule_root'

    generic_rule = fields.Many2One('ins_product.generic_business_rule',
                                   'Generic Rule')
    template = fields.Many2One(None, 'Template',
        domain=[('id', '!=', Eval('id'))])

    @classmethod
    def __setup__(cls):
        super(BusinessRuleRoot, cls).__setup__()
        cls.template = copy.copy(cls.template)
        cls.template.model_name = cls.__name__


class PricingRule(CoopSQL, BusinessRuleRoot):
    'Pricing Rule'

    __name__ = 'ins_product.pricing_rule'

    price = fields.Numeric('Amount', digits=(16, 2), required=True)


class EligibilityRule(CoopSQL, BusinessRuleRoot):
    'Eligibility Rule'

    __name__ = 'ins_product.eligibility_rule'

    is_eligible = fields.Boolean('Is Eligible')

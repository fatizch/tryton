#-*- coding:utf-8 -*-
import copy
import datetime

from trytond.model import ModelView, ModelSQL, fields as fields
from trytond.pool import Pool
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.rpc import RPC

from trytond.modules.coop_utils import utils as utils

__all__ = ['Coverage', 'Product', 'ProductOptionsCoverage',
           'BusinessRuleManager', 'GenericBusinessRule',
           'PricingRule', 'EligibilityRule']


class Offered(object):
    'Offered'

    code = fields.Char('Code', size=10, required=True, select=1)
    name = fields.Char('Name', required=True, select=1)
    start_date = fields.Date('Start Date', required=True, select=1)
    end_date = fields.Date('End Date')
    pricing_mgr = fields.Many2One('ins_product.business_rule_manager',
        'Pricing Manager',
        domain=[('business_rules.kind', '=', 'ins_product.pricing_rule')])
    eligibility_mgr = fields.Many2One('ins_product.business_rule_manager',
        'Eligibility Manager',
        domain=[('business_rules.kind', '=', 'ins_product.eligibility_rule')])

    @classmethod
    def __setup__(cls):
        for field_name, field in cls._columns.iteritems():
            if hasattr(field, 'context') and field_name.endswith('mgr'):
                cur_attr = getattr(cls, field_name)
                if cur_attr.context is None:
                    cur_attr.context = {}
                cur_attr.context['mgr'] = field_name
                setattr(cls, field_name, copy.copy(cur_attr))


class Coverage(ModelSQL, ModelView, Offered):
    'Coverage'

    __name__ = 'ins_product.coverage'


class Product(ModelSQL, ModelView, Offered):
    'Product'

    __name__ = 'ins_product.product'

    options = fields.Many2Many('ins_product-options-coverage', 'product',
                               'coverage', 'Options')


class ProductOptionsCoverage(ModelSQL):
    'Define Product - Coverage relations'

    __name__ = 'ins_product-options-coverage'

    product = fields.Many2One('ins_product.product',
                              'Product',
                              select=1,
                              required=True)
    coverage = fields.Many2One('ins_product.coverage',
                               'Coverage',
                               select=1,
                               required=True)


class BusinessRuleManager(ModelSQL, ModelView):
    'Business Rule Manager'

    __name__ = 'ins_product.business_rule_manager'

    belongs_to = fields.Function(
        fields.Reference('belongs_to', selection='get_offered_models'),
        'get_belongs_to')
    business_rules = fields.One2Many('ins_product.generic_business_rule',
        'manager', 'Business Rules', on_change=['business_rules'],
        context={'start_date': Eval('start_date')})

    @classmethod
    def __super__(cls):
        super(BusinessRuleManager, cls).__super__()
        cls.__rpc__.update({'get_offered_models': RPC(readonly=False)})

    @staticmethod
    def get_offered_models():
        return utils.get_descendents(Offered)

    def get_belongs_to(self, name):
        for offered_model, offered_name in self.get_offered_models():
            Offered = Pool().get(offered_model)
            field_name = Transaction().context.get('mgr')
            offered = Offered.search([(field_name, '=', self.id)])
            if offered is not None:
                return '%s, %s' % (offered_model, offered.id)
        return ''

    def on_change_business_rules(self):
        res = {'business_rules': {}}
        res['business_rules'].setdefault('update', [])
        for business_rule1 in self.business_rules:
            #the idea is to always set the end_date
            #to the according next start_date
            for business_rule2 in self.business_rules:
                if (business_rule1.get('id') != business_rule2.get('id') and
                    business_rule2['start_date'] is not None
                    and business_rule1['start_date'] is not None and
                    business_rule2['start_date'] > business_rule1['start_date']
                    and (business_rule1['end_date'] is None or
                         business_rule1['end_date'] >=
                         business_rule2['start_date'])):
                    end_date = (business_rule2['start_date']
                               - datetime.timedelta(days=1))
                    res['business_rules']['update'].append({
                        'id': business_rule1.get('id'),
                        'end_date': end_date})

            #if we change the start_date to a date after the end_date,
            #we reinitialize the end_date
            if (business_rule1['end_date'] is not None
                and business_rule1['end_date'] < business_rule1['start_date']):
                res['business_rules']['update'].append({
                        'id': business_rule1.get('id'),
                        'end_date': None})
        return res

    def get_good_rule_at_date(self, rulemanager, data):
        Business_rule = Pool().get('ins_product.generic_business_rule')
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
            good_rule, = Business_rule.search([
                                ('start_date', '<=', the_date),
                                ('manager', '=', rulemanager.id)
                                ],
                                order=[('start_date', 'DESC')],
                                limit=1)
            return good_rule
        except ValueError, exception:
            return None


class GenericBusinessRule(ModelSQL, ModelView):
    'Generic Business Rule'

    __name__ = 'ins_product.generic_business_rule'

    kind = fields.Selection('get_kind', 'Kind',
                            required=True, on_change=['kind'])
    manager = fields.Many2One('ins_product.business_rule_manager', 'Manager')
    start_date = fields.Date('From Date', required=True)
    end_date = fields.Date('To Date')
    is_current = fields.Function(fields.Boolean('Is current',
        on_change_with=['start_date', 'end_date']),
        'get_is_current')
    pricing_rule = fields.One2Many('ins_product.pricing_rule',
        'generic_rule', 'Pricing Rule')
    eligibilty_rule = fields.One2Many('ins_product.eligibility_rule',
        'generic_rule', 'Eligibility Rule')

    @classmethod
    def __setup__(cls):
        super(GenericBusinessRule, cls).__setup__()
#        cls.kind = copy.copy(cls.kind)
#        for field_name, field in cls._columns.iteritems():
#            if (hasattr(field, 'model_name')
#                and getattr(field, 'model_name').endswith('_rule')):
#                if cls.kind.on_change is None:
#                    cls.kind.on_change = []
#                if field_name  not in cls.kind.on_change:
#                    cls.kind.on_change += [field_name]
#
#                attr = getattr(cls, field_name)
#                attr.states = {
#                    'invisible': (Eval('kind') != field.model_name)}
#                setattr(cls, field_name, copy.copy(attr))

        cls.__rpc__.update({'is_current': RPC(readonly=False),
                             'on_change_kind': RPC(readonly=False)})
        cls._order.insert(0, ('start_date', 'ASC'))
        cls._constraints += [('check_dates', 'businessrule_overlaps')]
        cls._error_messages.update({'businessrule_overlaps':
            'You can not have 2 business rules that overlaps!'})

    def on_change_kind(self):
        res = {}
        for field_name, field in self._columns.iteritems():
            if (hasattr(field, 'model_name')
                and getattr(field, 'model_name').endswith('_rule')
                and len(getattr(self, field_name) == 0)):
                res[field_name] = {}
                if field.model_name == self.kind:
                    res[field_name]['add'] = [{}]
        return res

    @staticmethod
    def get_kind():
        return utils.get_descendents_name(BusinessRuleRoot)

#    def _getdefaults(self):
#        '''This method is called whenever we want to have access to _defaults
#        this is a hack to create an inline method whisch will instanciate
#        for each business rules the first element in the list.Only the visible
#        object will be instanciated'''
#
#        res = super(GenericBusinessRule, self)._getdefaults()
#
#        #Let's define a curry method to encapsulate the call with a parameter
#        def default_rule(for_name=''):
#            if Eval('kind') == for_name:
#                return [{}]
#            return []
#
#        for field_name, field in self._columns.iteritems():
#            if (hasattr(field, 'model_name')
#                and getattr(field, 'model_name')[-5:] == '_rule'):
#                res[field_name] = utils.curry(
#                    default_rule, for_name=field.model_name)
#
#        self.__defaults = res
#        return res
#    _defaults = property(fget=_getdefaults)

    def get_is_current(self, name):
        BRM = Pool().get('ins_product.business_self_manager')
        return self == BRM.get_good_rule_at_date(self.manager,
                {'date': datetime.date.today()})

    def on_change_with_is_current(self):
        return (datetime.date.today() >= self.start_date and
                (self.end_date is None or
                 datetime.date.today() <= self.end_date))

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


class BusinessRuleRoot(ModelSQL, ModelView):
    'Business Rule Root'

    generic_rule = fields.Many2One('ins_product.generic_business_rule',
                                   'Generic Rule')


class PricingRule(BusinessRuleRoot):
    'Pricing Rule'

    __name__ = 'ins_product.pricing_rule'

    price = fields.Numeric('Amount', digits=(16, 2), required=True)


class EligibilityRule(BusinessRuleRoot):
    'Eligibility Rule'

    __name__ = 'ins_product.eligibility_rule'

    is_eligible = fields.Boolean('Is Eligible')

#-*- coding:utf-8 -*-
import copy
import datetime

from trytond.model import ModelView, ModelSQL, fields as fields
from trytond.pool import Pool
from trytond.pyson import Eval
from trytond.transaction import Transaction

from trytond.modules.coop_utils import utils as utils


class Offered(object):
    'Offered'

    _description = __doc__

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

    def __init__(self):
        for field_name, field in self._columns.iteritems():
            if hasattr(field, 'context') and field_name.endswith('mgr'):
                cur_attr = getattr(self, field_name)
                if cur_attr.context is None:
                    cur_attr.context = {}
                cur_attr.context['mgr'] = field_name
                setattr(self, field_name, copy.copy(cur_attr))
        self._reset_columns()


class Coverage(ModelSQL, ModelView, Offered):
    'Coverage'

    _name = 'ins_product.coverage'
    _description = __doc__

Coverage()


class Product(ModelSQL, ModelView, Offered):
    'Product'

    _name = 'ins_product.product'
    _description = __doc__

    options = fields.Many2Many('ins_product-options-coverage', 'product',
                               'coverage', 'Options')

Product()


class ProductOptionsCoverage(ModelSQL):
    'Define Product - Coverage relations'

    _name = 'ins_product-options-coverage'

    product = fields.Many2One('ins_product.product',
                              'Product',
                              select=1,
                              required=True)
    coverage = fields.Many2One('ins_product.coverage',
                               'Coverage',
                               select=1,
                               required=True)

ProductOptionsCoverage()


class BusinessRuleManager(ModelSQL, ModelView):
    'Business Rule Manager'

    _name = 'ins_product.business_rule_manager'
    _description = __doc__

    belongs_to = fields.Function(
        fields.Reference('belongs_to', selection='get_offered_models'),
        'get_belongs_to')
    business_rules = fields.One2Many('ins_product.generic_business_rule',
        'manager', 'Business Rules', on_change=['business_rules'],
        context={'start_date': Eval('start_date')})

    def __init__(self):
        super(BusinessRuleManager, self).__init__()
        self._rpc.update({'get_offered_models': True})

    def get_offered_models(self):
        return utils.get_descendents(Offered)

    def get_belongs_to(self, ids, name):
        belongs = dict([(x, None) for x in ids])
        for offered_model, offered_name in self.get_offered_models():
            offered_obj = Pool().get(offered_model)
            field_name = Transaction().context.get('mgr')
            offered_ids = offered_obj.search([(field_name, 'in', ids)])
            for offered in offered_obj.browse(offered_ids):
                belongs[getattr(offered, field_name).id] = '%s, %s' \
                                        % (offered_model, offered.id)
        return belongs

    def on_change_business_rules(self, vals):
        res = {'business_rules': {}}
        res['business_rules'].setdefault('update', [])
        for business_rule1 in vals['business_rules']:
            #the idea is to always set the end_date
            #to the according next start_date
            for business_rule2 in vals['business_rules']:
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
        business_rule_obj = Pool().get('ins_product.generic_business_rule')
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
            good_id, = business_rule_obj.search([
                                ('start_date', '<=', the_date),
                                ('manager', '=', rulemanager.id)
                                ],
                                order=[('start_date', 'DESC')],
                                limit=1)
            return good_id
        except ValueError, exception:
            return None

BusinessRuleManager()


class GenericBusinessRule(ModelSQL, ModelView):
    'Generic Business Rule'

    _name = 'ins_product.generic_business_rule'
    _description = __doc__

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

    def __init__(self):
        super(GenericBusinessRule, self).__init__()
        self.kind = copy.copy(self.kind)
        for field_name, field in self._columns.iteritems():
            if (hasattr(field, 'model_name')
                and getattr(field, 'model_name').endswith('_rule')):
                if self.kind.on_change is None:
                    self.kind.on_change = []
                if field_name  not in self.kind.on_change:
                    self.kind.on_change += [field_name]

                attr = getattr(self, field_name)
                attr.states = {
                    'invisible': (Eval('kind') != field.model_name)}
                setattr(self, field_name, copy.copy(attr))
        self._reset_columns()

        self._rpc.update({'is_current': True, 'on_change_kind': True})
        self._order.insert(0, ('start_date', 'ASC'))
        self._constraints += [('check_dates', 'businessrule_overlaps')]
        self._error_messages.update({'businessrule_overlaps':
            'You can not have 2 business rules that overlaps!'})

    def on_change_kind(self, vals):
        res = {}
        for field_name, field in self._columns.iteritems():
            if (hasattr(field, 'model_name')
                and getattr(field, 'model_name').endswith('_rule')
                and len(vals[field_name]) == 0):
                res[field_name] = {}
                if field.model_name == vals['kind']:
                    res[field_name]['add'] = [{}]
        return res

    def get_kind(self):
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

    def get_is_current(self, ids, name):
        res = {}
        brm_obj = Pool().get('ins_product.business_rule_manager')
        for rule in self.browse(ids):
            if rule.id == brm_obj.get_good_rule_at_date(rule.manager,
                                          {'date': datetime.date.today()}):
                res[rule.id] = True
            else:
                res[rule.id] = False
        return res

    def on_change_with_is_current(self, vals):
        return (datetime.date.today() >= vals['start_date'] and
                (vals['end_date'] is None or
                 datetime.date.today() <= vals['end_date']))

    def check_dates(self, ids):
        cursor = Transaction().cursor
        for business_rule in self.browse(ids):
            cursor.execute('SELECT id ' \
                    'FROM ' + self._table + ' ' \
                    'WHERE ((start_date <= %s AND end_date >= %s) ' \
                            'OR (start_date <= %s AND end_date >= %s) ' \
                            'OR (start_date >= %s AND end_date <= %s)) ' \
                        'AND manager = %s ' \
                        'AND id != %s',
                    (business_rule.start_date, business_rule.start_date,
                        business_rule.end_date, business_rule.end_date,
                        business_rule.start_date, business_rule.end_date,
                        business_rule.manager.id, business_rule.id))
            if cursor.fetchone():
                return False
        return True

    def default_start_date(self):
        return Transaction().context.get('start_date')

GenericBusinessRule()


class BusinessRuleRoot(ModelSQL, ModelView):
    'Business Rule Root'

    _description = __doc__

    generic_rule = fields.Many2One('ins_product.generic_business_rule',
                                   'Generic Rule')


class PricingRule(BusinessRuleRoot):
    'Pricing Rule'

    _description = __doc__
    _name = 'ins_product.pricing_rule'

    price = fields.Numeric('Amount', digits=(16, 2), required=True)

PricingRule()


class EligibilityRule(BusinessRuleRoot):
    'Eligibility Rule'

    _description = __doc__
    _name = 'ins_product.eligibility_rule'

    is_eligible = fields.Boolean('Is Eligible')

EligibilityRule()


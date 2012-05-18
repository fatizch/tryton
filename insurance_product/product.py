#-*- coding:utf-8 -*-
import copy
import datetime

from trytond.model import ModelView, ModelSQL, fields as fields
from trytond.pool import Pool
from trytond.pyson import Eval

import coop_utils


class Offered(object):
    'Offered'

    _description = __doc__

    code = fields.Char('Code', size=10, required=True, select=1)
    name = fields.Char('Name', required=True, select=1)
    effective_date = fields.Date('Effective Date', required=True, select=1)
    end_date = fields.Date('End Date')
    pricing_mgr = fields.Many2One('ins_product.businessrulemanager',
        'Pricing Manager',
        domain=[('business_rules.kind', '=', 'ins_product.pricing_rule')])
    eligibility_mgr = fields.Many2One('ins_product.businessrulemanager',
        'Eligibility Manager',
        domain=[('business_rules.kind', '=', 'ins_product.eligibility_rule')])


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

    _name = 'ins_product.businessrulemanager'
    _description = __doc__

    business_rules = fields.One2Many('ins_product.genericbusinessrule',
        'manager', 'Business Rules')

    def on_change_2business_rules(self, vals):
        res = []
#        for business_rule in vals['business_rules']:
#            try:
#                business_rule['to_date'] = business_rule['from_date']
#            except KeyError:
#                pass
#            res.append(business_rule)
#        return {'business_rules': []}


        return {'toto': str(int(vals['toto']) + 1)}

    def get_good_rule_at_date(self, rulemanager, data):
        business_rule_obj = Pool().get('ins_product.genericbusinessrule')
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
                                ('from_date', '<=', the_date),
                                ('manager', '=', rulemanager.id)
                                ],
                                order=[('from_date', 'DESC')],
                                limit=1)
            return good_id
        except ValueError, exception:
            print "Exception : %s " % exception
            return None

BusinessRuleManager()


class GenericBusinessRule(ModelSQL, ModelView):
    'Generic Business Rule'

    _name = 'ins_product.genericbusinessrule'
    _description = __doc__

    kind = fields.Selection('get_kind', 'Kind',
                            required=True, on_change=['kind'])
    name = fields.Char('Name', required=True)
    manager = fields.Many2One('ins_product.businessrulemanager', 'Manager')
    from_date = fields.Date('From Date', required=True)
    to_date = fields.Date('To Date')
    is_current = fields.Function(fields.Boolean('Is current',
        on_change_with=['from_date', 'to_date',
                        '_parent_manager']),
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
                and getattr(field, 'model_name')[-5:] == '_rule'):
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

    def on_change_kind(self, vals):
        res = {}
        for field_name, field in self._columns.iteritems():
            if (hasattr(field, 'model_name')
                and getattr(field, 'model_name')[-5:] == '_rule'
                and len(vals[field_name]) == 0):
                res[field_name] = {}
                if field.model_name == vals['kind']:
                    res[field_name]['add'] = [{}]
        return res

    def get_kind(self):
        return coop_utils.get_descendents_name(BusinessRuleRoot)

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
#                res[field_name] = coop_utils.curry(
#                    default_rule, for_name=field.model_name)
#
#        self.__defaults = res
#        return res
#    _defaults = property(fget=_getdefaults)

    def get_is_current(self, ids, name):
        res = {}
        brm_obj = Pool().get('ins_product.businessrulemanager')
        for rule in self.browse(ids):
            if rule.id == brm_obj.get_good_rule_at_date(rule.manager,
                                          {'date': datetime.date.today()}):
                res[rule.id] = True
            else:
                res[rule.id] = False
        return res

    def on_change_with_is_current(self, vals):
        pass

GenericBusinessRule()


class BusinessRuleRoot(ModelSQL, ModelView):
    'Business Rule Root'

    _description = __doc__

    generic_rule = fields.Many2One('ins_product.genericbusinessrule',
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

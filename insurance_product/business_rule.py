#-*- coding:utf-8 -*-
import copy
import datetime

from trytond.model import ModelView, ModelSQL, fields as fields
from trytond.pool import Pool

from coop_utils import get_descendents, get_descendents_name
#from product import Offered


class BusinessRuleManager(object):
    'Business rule manager'

    _description = __doc__
    _name = ''

    kind = fields.Selection('get_kind', 'Kind', required=True)
    kind2 = fields.Many2One
    name = fields.Char('Name', required=True, select=1)
    code = fields.Char('Code', size=10, required=True, select=1)

    # It seems that tryton does not allow us to easily inherit as we are
    # used to.
    # Here, we would like to create a link to the abstract Offered class, but
    # we cannot do it so easily. We got to know which model to use in order to
    # create a Many2One field. So we create two of them, one for each subclass.
    '''for_coverage = fields.Many2One('ins_product.coverage', 'Belongs to')
    for_product = fields.Many2One('ins_product.product', 'Belongs to')
    # Then we use a function field behaving like a reference in order to create
    # an abstract access point, for which we will not know the class a priori,
    # just that it is a subclass of Offered.
    belongs_to = fields.Function(
        fields.Reference('belongs_to', selection='get_offered_models'),
        'get_belongs_to')'''
    business_rules = fields.One2Many(None, 'manager',
        'Business rules',
        required=True)

    def __init__(self):
        super(BusinessRuleManager, self).__init__()
        # Ajout de la contrainte SQL permettant d'être certain que le lien
        # belongs_to est unique,
        # quand bien même il est physiquement réparti dans deux
        # colonnes différentes
        '''self._sql_constraints += [('brm_belongs_to_unicity',
            \'''CHECK(
                        (FOR_COVERAGE IS NULL AND FOR_PRODUCT IS NOT NULL)
                    OR
                        (FOR_COVERAGE IS NOT NULL AND FOR_PRODUCT IS NULL)
                    )\''',
            'There must be a product or a coverage')]
        # We got to add this method to the pool of callable methods
        # for this class
        self._rpc.update({'get_offered_models': True})
'''
        self.business_rules = copy.copy(self.business_rules)
        '''self.business_rules.context = copy.copy(self.business_rules.context)
        self.business_rules.context['parent_kind'] = self._name'''
        self.business_rules.model_name = self.get_business_rule_model()
        self._reset_columns()

    def get_offered_models(self):
        #return get_descendents(Offered)
        pass

    def get_kind(self):
        raise NotImplementedError

    '''
    def get_belongs_to(self, ids, name):
        \'''
            We will use this field as an accessor to either for_product
            or for_coverage, depending on which one exists.
        \'''
        belongs = {}
        # So we first get the brm we want to work on
        for brm in self.browse(ids):
            # Then return either for_coverage or for_product.
            # The belongs_to function field behaves as a reference, so we
            # must return a tuple (model_name,instance_id) :
            if brm.for_coverage:
                belongs[brm.id] = 'ins_product.coverage,%s' \
                                    % brm.for_coverage.id
            elif brm.for_product:
                belongs[brm.id] = 'ins_product.product,%s' \
                                    % brm.for_product.id
            else:
                belongs[brm.id] = None
        return belongs
    '''
    def get_business_rule_model(self):
        pass

    def get_good_rule_at_date(self, rulemanager, data):
        '''
            This is the template of all rule managers calls :
                you got the rule manager and the data, give me back the
                appropriate rule !
        '''
        business_rule_obj = Pool().get('ins_product.businessrule')
        # First we got to check that the fields that we will need to calculate
        # which rule is appliable are available in the data dictionnary
        try:
            the_date = data['date']
        except KeyError:
            return None

        # If they exist, here we go :
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

    def calculate(self, rulemanager, data):
        rule_id = self.get_good_rule_at_date(rulemanager, data)
        if rule_id is None:
            return None
        rule_obj = Pool().get('ins_product.businessrule')
        return rule_obj.calculate([rule_id], data)


class OfferedRuleManager(ModelView):

    belongs_to = fields.Function(
        fields.Reference('Belongs to', selection='get_belongs_to_reference'),
        'get_belongs_to')
    for_offered = fields.Many2One(None, 'Offered')

    def __init__(self):
        super(OfferedRuleManager, self).__init__()
        self.for_offered = copy.copy(self.for_offered)
        self.for_offered.model_name = self.get_offered_kind()
        self._reset_columns()

        self._rpc.update({'get_belongs_to_reference': True})
        #self._rpc.update({'fields_view_get': True})

    def get_belongs_to_reference(self):
        #return get_descendents(Offered)
        pass

    def get_offered_kind(self):
        pass

    def get_belongs_to(self, ids, name):
        belongs = {}
        for brm in self.browse(ids):
            belongs[brm.id] = self.get_offered_kind()\
            + ',%s' % brm.for_offered.id
        return belongs


class ProductRuleManager(OfferedRuleManager):

    def get_kind(self):
        return get_descendents_name(BusinessRule, ProductRuleManager)

    def get_offered_kind(self):
        return 'ins_product.product'


class CoverageRuleManager(OfferedRuleManager):

    def get_kind(self):
        return get_descendents_name(BusinessRule, CoverageRuleManager)

    def get_offered_kind(self):
        return 'ins_product.coverage'


class PricingRuleManager(BusinessRuleManager):
    'Pricing Rule Manager'


class BusinessRule(ModelView):
    'Business rule'

    _description = __doc__

    name = fields.Char('Name', required=True, select=1)
    code = fields.Char('Code', size=10, required=True, select=1)
    from_date = fields.Date('From Date',
        required=True,
        on_change=['is_current'])
    to_date = fields.Date('To Date', on_change=['is_current'])
    is_current = fields.Function(fields.Boolean('Is current',
        on_change_with=['_parent_manager_business_rules']),
        'get_is_current')
    manager = fields.Many2One(None, 'Manager', required=True)

    def __init__(self):
        super(BusinessRule, self).__init__()
        self.manager = copy.copy(self.manager)
        self.manager.model_name = self.get_manager_model()
        self._reset_columns()

        #self._rpc.update({'get_is_current': True})

    def get_manager_model(self):
        pass

    def delete(self, ids):
        # We are using a fields.Reference attribute in this class.
        # We must ensure that it will be deleted properly when the current
        # object will be terminated.
        to_delete = {}
        # We go through all the provided ids
        for br in self.browse(ids):
            # setdefault = dictionnary method which returns the value
            # associated to the key (1st argument) if it exists, or
            # the second argument if it does not
            #
            # Here, we use it to create a dictionnary containing all the models
            # of the extension we are going to have to delete as keys,
            # and the list of ids to delete as values.
            to_delete.setdefault(br.extension.model, [])\
                                .append(br.extension.id)
        # Now, we just got to go through those models, and delete the
        # associated ids
        for model, model_ids in to_delete.items():
            model.delete(model_ids)
        # Do not forget to call the 'real' delete method !
        super(BusinessRule, self).delete(ids)

    def calculate(self, ids, data):
        res = {}
        # Easy one : we got a list of ids, so we just go through each of them,
        # get a browse object, then call the calculate function on its
        # extension with the provided data argument
        for rule in self.browse(ids):
            res[rule.id] = rule.extension.model.calculate(rule.extension, data)
        return res

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


class ProductPricingRuleManager(ModelSQL, ProductRuleManager,
                                PricingRuleManager):
    _name = 'ins_product.product_pricingrulemanager'

    def get_business_rule_model(self):
        return 'ins_product.product_pricingrule'

ProductPricingRuleManager()


class CoveragePricingRuleManager(ModelSQL, CoverageRuleManager,
                                 PricingRuleManager):
    _name = 'ins_product.coverage_pricingrulemanager'

    def get_business_rule_model(self):
        return 'ins_product.coverage_pricingrule'

CoveragePricingRuleManager()


class PricingRule(BusinessRule):
    'Pricing Rule'

    value = fields.Numeric('Rate', digits=(16, 2))

    def get_rule_kind(self, ids, name):
        # This method will allow this class to be used by a pricing business
        # rule manager
        return dict([(cur_id, 'Pricing') for cur_id in ids])

    def calculate(self, rule, data):
        # Easy one, the argument is the rule object (and not its id), so
        # we just have to get the value field and return it.
        return rule.value


class ProductPricingRule(ModelSQL, PricingRule):
    __doc__ = PricingRule.__doc__
    _name = 'ins_product.product_pricingrule'

    def get_manager_model(self):
        return 'ins_product.product_pricingrulemanager'

ProductPricingRule()


class CoveragePricingRule(ModelSQL, PricingRule):
    __doc__ = PricingRule.__doc__
    _name = 'ins_product.coverage_pricingrule'

    def get_manager_model(self):
        return 'ins_product.coverage_pricingrulemanager'

CoveragePricingRule()


class EligibilityRuleManager(BusinessRuleManager):
    'Eligibility Rule Manager'


class ProductEligibilityRuleManager(ModelSQL, ProductRuleManager,
                                    EligibilityRuleManager):
    _name = 'ins_product.product_eligibilityrulemanager'

    def get_business_rule_model(self):
        return 'ins_product.product_eligibilityrule'

ProductEligibilityRuleManager()


class CoverageEligibilityRuleManager(ModelSQL, CoverageRuleManager,
                                     EligibilityRuleManager):
    _name = 'ins_product.coverage_eligibilityrulemanager'

    def get_business_rule_model(self):
        return 'ins_product.coverage_eligibilityrule'

CoverageEligibilityRuleManager()


class EligibilityRule(BusinessRule):
    'Eligibility Rule'

    age_min = fields.Integer('Minimum Age')
    age_max = fields.Integer('Maximum Age')

    def get_rule_kind(self, ids, name):
        return dict([(cur_id, 'Eligibility') for cur_id in ids])

    def calculate(self, rule, data):
        pass


class ProductEligibilityRule(EligibilityRule):
    __doc__ = EligibilityRule.__doc__
    _name = 'ins_product.product_eligibilityrule'

    toto = fields.Char('Toto')
    def get_manager_model(self):
        return 'ins_product.product_eligibilityrulemanager'

ProductEligibilityRule()


class CoverageEligibilityRule(EligibilityRule):
    __doc__ = EligibilityRule.__doc__
    _name = 'ins_product.coverage_eligibilityrule'

    def get_manager_model(self):
        return 'ins_product.coverage_eligibilityrulemanager'

CoverageEligibilityRule()


class FakeBusinessRule(ModelSQL, ModelView):
    'Business Rule'

    _name = 'ins_product.business_rule2'
    _description = __doc__

    name = fields.Char('Name')
    pricing_rule = fields.One2One('ins_product.pricing_rule',
        'link', 'id', 'Pricing Rule')
    pricing_rules = fields.One2Many('ins_product.pricing_rule',
                                    'link', 'Pricing rules')

FakeBusinessRule()


class PricingBusinessRule2(ModelSQL, ModelView):
    'Pricing Rule'

    _name = 'ins_product.pricing_rule'
    _description = __doc__

    name = fields.Char('Name')
    link = fields.Many2One('ins_product.business_rule2', 'Link')

PricingBusinessRule2()

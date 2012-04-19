#-*- coding:utf-8 -*-
import copy
import datetime

from trytond.model import ModelView, ModelSQL, fields as fields
from trytond.pyson import Eval
from trytond.pool import Pool
from trytond.transaction import Transaction

RULE_TYPES = [
                ('Pricing', 'Pricing'),
                ('Eligibility', 'Eligibility'),
                ('Termination', 'Termination'),
                ('Underwriting', 'Underwriting'),
             ]
EXTENSION_TYPES = [
                   ('Disability', 'Disability'),
                   ('Annuity', 'Annuity'),
                   ('Pension', 'Pension'),
                   ('Credit', 'Credit Insurance')]


class Offered(object):
    'Offered'
    name = fields.Char('Name', required=True, select=1)
    code = fields.Char('Code', size=10, required=True, select=1)
    effective_date = fields.Date('Effective Date', required=True, select=1)
    end_date = fields.Date('End Date',)
    managers = fields.One2Many('ins_product.businessrulemanager',
                               None,
                               'Business rule managers')

    def calculate(self, ids, data, rule_kind):
        '''
            Calculate is the method which will call the business
            intelligence, looking for the good rule manager depending
            on the provided rule_kind

            The 'ids' argument contains a list of Offered ids, which
            represents the set of elements we want the rule applied to.
        '''
        # Pool allows us to get the model object, which represents all
        # 'instances' of the class businessrulemanager. It is this object
        # that we will use to call methods, providing a list of ids to treat
        brm_obj = Pool.get('ins_product.businessrulemanager')

        # The result will be a dictionnary in order to be able to return
        # a different result for each of the ids provided as arguments
        result = {}
        if not [rule for rule in RULE_TYPES if rule[0] == rule_kind]:
            # If the requested rule does not exist, we return a dictionnary
            # with empty answers
            return dict((curid, (None, ['wrong_rule_kind'])) for curid in ids)
        # Else, we treat each id with the browse method, to get the associated
        # object
        for offered in self.browse(ids):
            # Once we got a browse object, we can call its attributes as
            # python attributes
            for brm in offered.managers:
                # We use != and continue rather than == in order to get
                # one level of indentation back
                if brm.rule_kind != rule_kind:
                    continue
                # Now we call the method on the model me got from Pool, passing
                # directly the object as an argument
                result[offered.id] = brm_obj.calculate(brm, data)
            # If we could not find a rule, or calculation did not happen for
            # some reason, we just return an error tuple as a result for
            # this id.
            if offered.id not in result:
                result[offered.id] = (None,
                                      ['inexisting_rule_kind_for_offered'])
        return result


class Coverage(ModelSQL, ModelView, Offered):
    'Coverage'
    _name = 'ins_product.coverage'
    _description = __doc__

    def __init__(self):
        # We want to inherit from Offered, which is not a tryton class.
        # We defined in offered a One2Many field with no backref, as we could
        # not the one to use.
        # Now that we are in an instanciated class, we can, so we just have
        # to override __init__ in order to tell to tryton, when it creates
        # the model, the managers field backref is 'for_coverage'
        super(Coverage, self).__init__()
        self.managers = copy.copy(self.managers)
        self.managers.field = 'for_coverage'
        # We must reset the columns in order to force tryton to refresh its
        # understanding of the model
        self._reset_columns()

Coverage()


class Product(ModelSQL, ModelView, Offered):
    'ins_product'
    _name = 'ins_product.product'
    _description = __doc__
    options = fields.Many2Many('ins_product-options-coverage', 'product',
                               'coverage', 'Options')

    def __init__(self):
        # cf Coverage.__init__ for details
        super(Product, self).__init__()
        self.managers = copy.copy(self.managers)
        self.managers.field = 'for_product'
        self._reset_columns()

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


class RuleInterface(object):
    'Generic Rule Interface'
    '''
        This class exists to create a template of the functions / attributes to
        which all rule classes will have to respond to.
    '''
    rule_kind = fields.Function(fields.Selection(RULE_TYPES, 'Rule Type'),
                                'get_rule_kind')

    def calculate(self, rule, data):
        # This method is going to give us a generic entry point to calculate
        # the result of any Rule we are going to use
        pass

    def get_rule_kind(self, ids, name):
        # This one will be used to decide which kind of rules will be allowed
        # for a given business rule manager (we got to make get_rule_kind on
        # the rule and rule_kind on the manager to match)
        pass


class PricingRule(ModelSQL, ModelView, RuleInterface):
    'Pricing Rule'
    '''
        This rule is an example of implementation of the RuleInterface
        interface :
        we add a field to contain its specific data, and override the
        two functions declared in the interface.
    '''
    _name = 'ins_product.pricingrule'
    _description = __doc__
    value = fields.Numeric('Rate', digits=(16, 2))

    def get_rule_kind(self, ids, name):
        # This method will allow this class to be used by a pricing business
        # rule manager
        return dict([(cur_id, 'Pricing') for cur_id in ids])

    def calculate(self, rule, data):
        # Easy one, the argument is the rule object (and not its id), so
        # we just have to get the value field and return it.
        return rule.value

PricingRule()


class EligibilityRule(ModelSQL, ModelView, RuleInterface):
    'Eligibility Rule'

    _name = 'ins_product.eligibilityrule'
    _description = __doc__
    age_min = fields.Integer('Minimum Age')
    age_max = fields.Integer('Maximum Age')

    def get_rule_kind(self, ids, name):
        return dict([(cur_id, 'Eligibility') for cur_id in ids])

    def calculate(self, rule, data):
        pass

    def test(self, ids):
            eligibility_obj = Pool().get('ins_product.eligibilityrule')
            for cur_eligibility in self.browse(ids):
                pass

EligibilityRule()


class BusinessRuleManager(ModelSQL, ModelView):
    'Business rule manager'
    _name = 'ins_product.businessrulemanager'
    _description = __doc__
    name = fields.Char('Name', required=True, select=1)
    code = fields.Char('Code', size=10, required=True, select=1)

    # It seems that tryton does not allow us to easily inherit as we are
    # used to.
    # Here, we would like to create a link to the abstract Offered class, but
    # we cannot do it so easily. We got to know which model to use in order to
    # create a Many2One field. So we create two of them, one for each subclass.
    for_coverage = fields.Many2One('ins_product.coverage', 'Belongs to')
    for_product = fields.Many2One('ins_product.product', 'Belongs to')
    # Then we use a function field behaving like a reference in order to create
    # an abstract access point, for which we will not know the class a priori,
    # just that it is a subclass of Offered.
    belongs_to = fields.Function(fields.Reference(
                                        'belongs_to',
                                        selection='get_offered_models'),
                                        'get_belongs_to')
    # This field will be used to find matching rule classes.
    rule_kind = fields.Selection(RULE_TYPES,
                                 'Rule Type')
    business_rules = fields.One2Many('ins_product.businessrule', 'manager',
        'Business rules',
        required=True,
        context={'manager': Eval('rule_kind')})

    def __init__(self):
        super(BusinessRuleManager, self).__init__()
        # Ajout de la contrainte SQL permettant d'être certain que le lien
        # belongs_to est unique,
        # quand bien même il est physiquement réparti dans deux
        # colonnes différentes
        self._sql_constraints += [('brm_belongs_to_unicity',
                                   '''CHECK
                                       (
                                           (FOR_COVERAGE IS NULL AND
                                           FOR_PRODUCT IS NOT NULL)
                                        OR
                                           (FOR_COVERAGE IS NOT NULL AND
                                           FOR_PRODUCT IS NULL)
                                        )''',
                                   'There must be a product or a coverage')]
        # We got to add this method to the pool of callable methods
        # for this class
        self._rpc.update({'get_offered_models': True})

    def get_offered_models(self):
        # cf get_rule_models
        # This is an alternate way to get our models.
        # First we get the names
        model_obj = Pool().get('ir.model')
        res = []
        offered_models = [model_name
                          for model_name, model in Pool().iterobject()
                          if isinstance(model, Offered)]
        # look for the objects in the model table
        model_ids = model_obj.search([
            ('model', 'in', offered_models),
            ])
        # then get the associated browse object, to finally get the
        # model.model and model.name
        for model in model_obj.browse(model_ids):
            res.append([model.model, model.name])
        return res

    def get_belongs_to(self, ids, name):
        '''
            We will use this field as an accessor to either for_product
            or for_coverage, depending on which one exists.
        '''
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
        return belongs

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


BusinessRuleManager()


class BusinessRule(ModelSQL, ModelView):
    'Business rule'
    _name = 'ins_product.businessrule'
    _description = __doc__
    name = fields.Char('Name', required=True, select=1)
    code = fields.Char('Code', size=10, required=True, select=1)
    from_date = fields.Date('From Date',
        required=True,
        on_change=['is_current'])
    manager = fields.Many2One('ins_product.businessrulemanager',
                              'Manager', required=True)
    extension = fields.Reference('Rule',
        selection='get_rule_models')
    # fields.Reference allows us to create a reference to an object without
    # knowing a priori its model. We can use the selection parameter to
    # specify a method which will be called to get a list containing the
    # allowed models.
    is_current = fields.Function(fields.Boolean('Is current',
                                            on_change_with=[
                                            '_parent_manager_business_rules']),
                                'get_is_current')

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

    def get_rule_models(self):
        '''
            This method is used to get the list of models that will be allowed
            when creating or using the extension field.
        '''
        # Then we go through all the objects of the Pool to find those
        # who match the criteria we are using (in this case, they must
        # inherit of RuleInterface)
        # Careful, we must return the _name and the __doc__ of the model.
        # model._name is NOT model_name !
        # For extra details, have a look at get_offered_models
        return [[model._name, model.__doc__]
                          for model_name, model in Pool().iterobject()
                          if isinstance(model, RuleInterface)]

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

        def on_change_with_extension(self, vals):
            pass

    def default_extension(self):
        return Transaction().context.get('rule_kind')

BusinessRule()

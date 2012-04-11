import copy

from trytond.model import ModelView, ModelSQL, fields
from trytond.pool import Pool

RULE_TYPES = [
                ('Pricing', 'Pricing'),
                ('Eligibility', 'Eligibility'),
                ('Termination', 'Termination'),
                ('Underwriting', 'Underwriting'),
             ]

class Offered(object):
    'Offered'
    name = fields.Char('Name', required=True, select=1)
    code = fields.Char('Code', size=10, required=True, select=1)
    effective_date = fields.Date('Effective Date', required=True, select=1)
    managers = fields.One2Many('ins_product.businessrulemanager',
                               None,
                               'Business rule managers')

    def calculate(self, ids, data, rule_kind):
        brm_obj = Pool.get('ins_product.businessrulemanager')
        result = {}
        if not [rule for rule in RULE_TYPES if rule[0] == rule_kind]:
            return dict((id, (None, ['wrong_rule_kind'])) for id in ids)
        for offered in self.browse(ids):
            for brm in offered.managers:
                if brm.rule_kind != rule_kind:
                    continue
                result[offered.id] = brm_obj.calculate(brm, data)
            if offered.id not in result:
                result[offered.id] = (None, ['inexisting_rule_kind_for_offered'])
        return result


class Coverage(ModelSQL, ModelView, Offered):
    'Coverage'
    _name = 'ins_product.coverage'
    _description = __doc__

    def __init__(self):
        super(Coverage, self).__init__()
        self.managers = copy.copy(self.managers)
        self.managers.field = 'for_coverage'
        # We must reset columns in order to allow tryton to understand
        # the new model
        self._reset_columns()

Coverage()


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


class Product(ModelSQL, ModelView, Offered):
    'ins_product'
    _name = 'ins_product.product'
    _description = __doc__
    options = fields.Many2Many('ins_product-options-coverage', 'product',
                               'coverage', 'Options')

    def __init__(self):
        super(Product, self).__init__()
        self.managers = copy.copy(self.managers)
        self.managers.field = 'for_product'
        self._reset_columns()

Product()


class BusinessRule(ModelSQL, ModelView):
    'Business rule'
    _name = 'ins_product.businessrule'
    _description = __doc__
    name = fields.Char('Name', required=True, select=1)
    code = fields.Char('Code', size=10, required=True, select=1)
    from_date = fields.Date('From Date', required=True)
    manager = fields.Many2One('ins_product.businessrulemanager',
                              'Manager', required=True)
    extension = fields.Reference('Rule',
                                 selection='get_rule_models')

    def delete(self, ids):
        to_delete = {}
        for br in self.browse(ids):
            # setdefault = dictionnary method which returns the value associated to the
            # key (1st argument) if it exists, or the second argument if it does not
            to_delete.setdefault(br.extension.model, []).append(br.extension.id)
        for model, model_ids in to_delete.items():
            model.delete(model_ids)
        super(BusinessRule, self).delete(ids)

    def get_rule_models(self):
        model_obj = Pool().get('ir.model')
        res = []
        offered_models = [model_name for model_name, model in Pool().iterobject()
                          if isinstance(model, RuleInterface)]
        model_ids = model_obj.search([
            ('model', 'in', offered_models),
            ])
        for model in model_obj.browse(model_ids):
            res.append([model.model, model.name])
        return res

    def calculate(self, ids, data):
        res = {}
        for rule in self.browse(ids):
            res[rule.id] = rule.extension.model.calculate(rule.extension, data)
        return res

BusinessRule()


class RuleInterface(object):
    rule_kind = fields.Function(fields.Selection(RULE_TYPES, 'Rule Type'),
                                'get_rule_kind')
    def calculate(self, rule, data):
        pass

    def get_rule_kind(self, ids, name):
        pass


class PricingRule(ModelSQL, ModelView, RuleInterface):
    'Pricing Rule'
    _name = 'ins_product.pricingrule'
    _description = __doc__
    value = fields.Numeric('Rate', digits=(16, 2))

    def get_rule_kind(self, ids, name):
        return dict([(id, 'Pricing') for id in ids])

    def calculate(self, rule, data):
        return rule.value

PricingRule()


class BusinessRuleManager(ModelSQL, ModelView):
    'Business rule manager'
    _name = 'ins_product.businessrulemanager'
    _description = __doc__
    name = fields.Char('Name', required=True, select=1)
    code = fields.Char('Code', size=10, required=True, select=1)
    for_coverage = fields.Many2One('ins_product.coverage', 'Belongs to')
    for_product = fields.Many2One('ins_product.product', 'Belongs to')
    business_rules = fields.One2Many('ins_product.businessrule', 'manager',
                                     'Business rules', required=True)
    belongs_to = fields.Function(fields.Reference('belongs_to',
                                                  selection='get_offered_models'),
                                  'get_belongs_to')
    # fields.Reference permet de référencer un objet sans connaître sa classe a priori.
    # Le paramètre selection permet de psécifier une focntion qui renverra une liste de 
    # noms de modèles autorisés.

    rule_kind = fields.Selection(RULE_TYPES,
                                 'Rule Type')

    def __init__(self):
        super(BusinessRuleManager, self).__init__()
        # Ajout de la contrainte SQL permettant d'être certain que le lien belongs_to est
        # unique quand bien même il est physiquement réparti dans deux colonnes différentes
        self._sql_constraints += [('brm_belongs_to_unicity',
                                   'CHECK ((FOR_COVERAGE IS NULL AND FOR_PRODUCT IS NOT NULL) OR \
                                   (FOR_COVERAGE IS NOT NULL AND FOR_PRODUCT IS NULL))',
                                   'There should be either a product or a coverage')]
        # We got to add this methos to the pool of callable methods for this class
        self._rpc.update({'get_offered_models': True})

    def get_offered_models(self):
        model_obj = Pool().get('ir.model')
        res = []
        offered_models = [model_name for model_name, model in Pool().iterobject()
                          if isinstance(model, Offered)]
        model_ids = model_obj.search([
            ('model', 'in', offered_models),
            ])
        for model in model_obj.browse(model_ids):
            res.append([model.model, model.name])
        return res

    def get_belongs_to(self, ids, name):
        belongs = {}
        for brm in self.browse(ids):
            if brm.for_coverage:
                belongs[brm.id] = 'ins_product.coverage,%s' % brm.for_coverage.id
            elif brm.for_product:
                belongs[brm.id] = 'ins_product.product,%s' % brm.for_product.id
        return belongs

    def get_good_rule_at_date(self, rulemanager, data):
        business_rule_obj = Pool().get('ins_product.businessrule')
        try:
            the_date = data['date']
        except KeyError:
            return None

        try:
            good_id, = business_rule_obj.search([('from_date', '<', the_date),
                                                 ('manager', '=', rulemanager.id)],
                                                 order='from_date DESC',
                                                 limit=1)
            return good_id
        except ValueError:
            return None

    def calculate(self, rulemanager, data):
        rule_id = self.get_good_rule_at_date(rulemanager, data)
        if rule_id is None:
            return None
        rule_obj = Pool().get('ins_product.businessrule')
        return rule_obj.calculate([rule_id], data)


BusinessRuleManager()

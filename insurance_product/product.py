#-*- coding:utf-8 -*-
import copy

from trytond.model import fields
from trytond.pool import Pool
from trytond.pyson import Eval, Bool
from trytond.transaction import Transaction

from trytond.modules.coop_utils import model, business, utils
from trytond.modules.insurance_product import PricingResultLine
from trytond.modules.insurance_product import EligibilityResultLine


__all__ = [
   'Offered',
   'Product',
   'ProductOptionsCoverage',
   'ProductDefinition',
    ]

CONFIG_KIND = [
    ('simple', 'Simple'),
    ('rule', 'Rule Engine')
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
        states={
            'invisible': ~Eval('template'),
        },
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
    _export_name = 'code'

    code = fields.Char('Code', required=True, select=1)
    name = fields.Char('Name', required=True, select=1)
    start_date = fields.Date('Start Date', required=True, select=1)
    end_date = fields.Date('End Date')
    description = fields.Text('Description')
    #All mgr var must be the same as the business rule class and ends with mgr
    pricing_mgr = model.One2ManyDomain('ins_product.business_rule_manager',
        'offered', 'Pricing Manager')
    eligibility_mgr = model.One2ManyDomain('ins_product.business_rule_manager',
        'offered', 'Eligibility Manager')
    clause_mgr = model.One2ManyDomain('ins_product.business_rule_manager',
        'offered', 'Clause Manager')
    deductible_mgr = model.One2ManyDomain('ins_product.business_rule_manager',
        'offered', 'Deductible Manager')
    summary = fields.Function(fields.Text('Summary',
            states={
                'invisible': ~Eval('summary',)
            }),
        'get_summary')
    currency_digits = fields.Function(fields.Integer('Currency Digits'),
        'get_currency_digits')
    dynamic_data_manager = model.One2ManyDomain(
        'ins_product.dynamic_data_manager',
        'master',
        'Complementary Data Manager',
        context={
            'schema_element_kind': 'contract',
            'for_kind': 'main'},
        domain=[('kind', '=', 'main')],
        size=1)
    offered_dynamic_data = fields.Dict(
        'Offered Kind',
        schema_model='ins_product.schema_element',
        context={
            'schema_element_kind': 'product'},
        domain=[('kind', '=', 'product')])

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

    def give_me_dynamic_data_ids(self, args):
        if not(hasattr(self,
                'dynamic_data_manager') and self.dynamic_data_manager):
            return []
        return self.dynamic_data_manager[0].get_valid_schemas_ids(
            args['date']), []

    @staticmethod
    def default_offered_dynamic_data():
        good_se = Pool().get('ins_product.schema_element').search([
            ('kind', '=', 'product')])
        res = {}
        for se in good_se:
            res[se.technical_name] = se.get_default_value(None)
        return res


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
    term_renewal_mgr = model.One2ManyDomain(
        'ins_product.business_rule_manager', 'offered', 'Term - Renewal')

    @classmethod
    def __setup__(cls):
        super(Product, cls).__setup__()
        #Temporary remove, while impossible to duplicate whith same code
#        cls._sql_constraints += [
#            ('code_uniq', 'UNIQUE(code)', 'The code must be unique!'),
#        ]

    @classmethod
    def delete(cls, entities):
        utils.delete_reference_backref(
            entities,
            'ins_product.business_rule_manager',
            'offered')
        utils.delete_reference_backref(
            entities,
            'ins_product.dynamic_data_manager',
            'master')
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

    def give_me_dynamic_data_ids_aggregate(self, args):
        if not 'dd_args' in args:
            return [], []
        res = set()
        errs = []
        for opt in self.options:
            result, errors = opt.get_result(
                'dynamic_data_ids_aggregate',
                args)
            map(lambda x: res.add(x), result)
            errs += errors
        return list(res), errs

    def give_me_dynamic_data_getter(self, args):
        if not 'dd_args' in args:
            return [], []
        dd_args = args['dd_args']
        if not 'path' in dd_args:
            if not 'options' in dd_args:
                return self.give_me_dynamic_data_ids(args)
            dd_args['path'] = 'all'
        return self.give_me_dynamic_data_ids_aggregate(args)

    @classmethod
    def search_options(cls, name, clause):
        super(Product, cls).search_options(name, clause)


class ProductOptionsCoverage(model.CoopSQL):
    'Define Product - Coverage relations'

    __name__ = 'ins_product.product-options-coverage'

    product = fields.Many2One('ins_product.product',
        'Product', select=1, required=True, ondelete='CASCADE')
    coverage = fields.Many2One('ins_product.coverage',
        'Coverage', select=1, required=True, ondelete='RESTRICT')


class ProductDefinition(model.CoopView):
    'Product Definition'

    # This class is the base of Product Definitions. It defines number of
    # methods which will be used to define a business family behaviour in
    # the application

    def get_extension_model(self):
        raise NotImplementedError

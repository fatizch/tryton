#-*- coding:utf-8 -*-
import copy

from trytond.pool import Pool
from trytond.pyson import Eval, Bool
from trytond.transaction import Transaction

from trytond.modules.coop_utils import model, business, utils, fields
from trytond.modules.coop_utils import coop_string
from trytond.modules.insurance_product import PricingResultLine
from trytond.modules.insurance_product import EligibilityResultLine


__all__ = [
    'GetResult',
    'Offered',
    'Product',
    'ProductOptionsCoverage',
    'ProductDefinition',
    'ItemDescriptor',
    'ItemDescriptorComplementaryDataRelation',
    'ProductItemDescriptorRelation',
    'ProductComplementaryDataRelation',
    'ExpenseKind',
]

CONFIG_KIND = [
    ('simple', 'Simple'),
    ('advanced', 'Advanced')
]

TEMPLATE_BEHAVIOUR = [
    ('', ''),
    ('pass', 'Add'),
    ('override', 'Remove'),
]

DEF_CUR_DIG = 2


class Templated(object):
    'Templated Class'

    __name__ = 'ins_product.templated'

    template = fields.Many2One(
        None, 'Template',
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
                return {'template_behaviour': 'pass'}
        else:
            return {'template_behaviour': None}


class NonExistingRuleKindException(Exception):
    pass


class GetResult(object):
    def get_result(self, target='result', args=None, kind='', path=''):
        # This method is a generic entry point for getting parameters.
        #
        # Arguments are :
        #  - The target value to compute. It is a key which will be used to
        #    decide which data is asked for
        #  - The dict of arguments which will be used by the rule to compute.
        #    Another way to do this would be a link to a method on the caller
        #    which would provide said args on demand.
        #  - The kind will usually be filled, it is a key to finding where
        #    the required data is stored. So if the target is "price", the
        #    kind should be set to "pricing".
        #  - We can use the 'path' arg to specify the way to our data.
        #    Basically, we try to match the first part of path (which looks
        #    like a '.' delimited string ('alpha1.beta3.gamma2')) to one of the
        #    sub-elements of self, then iterate.

        if path:
            # If a path is set, the data we look for is not set on self. So we
            # need to iterate on self's sub-elems.
            #
            # First of all, we need the sub-elems descriptor. This is the
            # result of the get_sub_elem_data method, which returns a tuple
            # with the field name to iterate on as the first element, and
            # this field's field on which to try to match the value.
            sub_elem_data = self.get_sub_elem_data()

            if not sub_elem_data:
                # If it does not exist, someone failed...
                return (None, ['Object %s does not have any sub_data.' % (
                    self.name)])

            path_elems = path.split('.')

            for elem in getattr(self, sub_elem_data[0]):
                # Now we iterate on the specified field
                if path_elems[0] in (
                        getattr(elem, attr) for attr in sub_elem_data[1]):
                    if isinstance(elem, GetResult):
                        return elem.get_result(
                            target, args, kind, '.'.join(path_elems[1:]))
                    return (
                        None, ['Sub element %s of %s cannot get_result !' % (
                            elem.name, self.name)])
            return (None, ['Could not find %s sub element in %s' % (
                path_elems[0], self.name)])

        if kind:
            try:
                good_rule = self.get_good_rule_at_date(args, kind)
            except Exception:
                good_rule = None
            if not good_rule:
                # We did not found any rule matching the specified name
                raise NonExistingRuleKindException
            return good_rule.get_result(target, args)

        # Now we look for our target, as it is at our level
        target_func = getattr(self, 'give_me_' + target)

        result = target_func(args)
        if not isinstance(result, tuple) and not result is None:
            return (result, [])
        return result

    def get_sub_elem_data(self):
        # Should be overridden
        return None


class Offered(model.CoopView, GetResult, Templated):
    'Offered'

    __name__ = 'ins_product.offered'
    _export_name = 'code'

    code = fields.Char('Code', required=True, select=1)
    name = fields.Char('Name', required=True, select=1, translate=True)
    start_date = fields.Date('Start Date', required=True, select=1)
    end_date = fields.Date('End Date')
    description = fields.Text('Description', translate=True)

    pricing_rules = fields.One2Many('ins_product.pricing_rule',
        'offered', 'Pricing Rules')
    eligibility_rules = fields.One2Many(
        'ins_product.eligibility_rule', 'offered', 'Eligibility Rules')
    clause_rules = fields.One2Many(
        'ins_product.clause_rule', 'offered', 'Clause Rules')
    deductible_rules = fields.One2Many(
        'ins_product.deductible_rule', 'offered', 'Deductible Rules')
    document_rules = fields.One2ManyDomain(
        'ins_product.document_rule', 'offered', 'Document Rules',
        context={'doc_rule_kind': 'main'},
        domain=[('kind', '=', 'main')])
    sub_document_rules = fields.One2ManyDomain(
        'ins_product.document_rule', 'offered', 'Sub Document Rules',
        context={'doc_rule_kind': 'sub'},
        domain=[('kind', '=', 'sub')])
    summary = fields.Function(
        fields.Text(
            'Summary', states={'invisible': ~Eval('summary',)}),
        'get_summary')
    currency_digits = fields.Function(
        fields.Integer('Currency Digits'),
        'get_currency_digits')
    complementary_data = fields.Dict(
        'ins_product.complementary_data_def', 'Offered Kind',
        context={'complementary_data_kind': 'product'},
        domain=[('kind', '=', 'product')],
        on_change_with=['complementary_data'])

    @classmethod
    def __setup__(cls):
        super(Offered, cls).__setup__()
        for field_name in (r for r in dir(cls) if r.endswith('_rules')):
            field = getattr(cls, field_name)
            if not hasattr(field, 'model_name'):
                continue
            cur_attr = copy.copy(field)
            if not hasattr(cur_attr, 'context'):
                continue
            if cur_attr.context is None:
                cur_attr.context = {}
            cur_attr.context['start_date'] = Eval('start_date')
            cur_attr.context['currency_digits'] = Eval('currency_digits')
            if cur_attr.depends is None:
                cur_attr.depends = []
            utils.extend_inexisting(
                cur_attr.depends, ['start_date', 'currency_digits'])
            if cur_attr.states is None:
                cur_attr.states = {}
            cur_attr.states['readonly'] = ~Bool(Eval('start_date'))

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

    @staticmethod
    def default_complementary_data():
        good_se = Pool().get('ins_product.complementary_data_def').search([
            ('kind', '=', 'product')])
        res = {}
        for se in good_se:
            res[se.name] = se.get_default_value(None)
        return res

    def get_good_rule_at_date(self, data, kind):
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
            return utils.get_good_version_at_date(
                self, '%s_rules' % kind, the_date)
        except ValueError:
            return None

    @classmethod
    def delete_rules(cls, entities):
        for field_name in (r for r in dir(cls) if r.endswith('_rules')):
            field = getattr(cls, field_name)
            if not hasattr(field, 'model_name'):
                continue
            utils.delete_reference_backref(
                entities, field.model_name, field.field)

    def get_complementary_data_def(self, kinds=None, at_date=None):
        return [
            x for x in self.complementary_data_def
            if x.valid_at_date(at_date) and (not kinds or x.kind in kinds)]

    def get_complementary_data_for_execution(self, args):
        looking_for = 'contract' if not 'sub_elem' in args else 'sub_elem'
        all_schemas = set(self.get_complementary_data_def(
            ('contract', looking_for), args['date']))
        possible_schemas = set(self.get_complementary_data_def(
            (looking_for), args['date']))
        return all_schemas, possible_schemas

    def give_me_sub_elem_eligibility(self, args):
        try:
            res = self.get_result(
                'sub_elem_eligibility', args, kind='eligibility')
        except NonExistingRuleKindException:
            return (EligibilityResultLine(True), [])
        return res

    def give_me_documents(self, args):
        try:
            return self.get_result('documents', args, kind='document')
        except NonExistingRuleKindException:
            return [], ()

    def on_change_with_complementary_data(self):
        if not hasattr(self, 'complementary_data_def'):
            return {}
        ComplementaryData = Pool().get('ins_product.complementary_data_def')
        schemas = ComplementaryData.search([
            'name', 'in', [k for k in self.complementary_data_def.iterkeys()]])
        if not schemas:
            return {}
        result = copy.copy(self.complementary_data_def)
        for schema in schemas:
            schema.update_field_value(result)
        return result


class Product(model.CoopSQL, Offered):
    'Product'

    __name__ = 'ins_product.product'

    options = fields.Many2Many(
        'ins_product.product-options-coverage',
        'product', 'coverage', 'Options',
        domain=[('currency', '=', Eval('currency'))],
        depends=['currency'])
    currency = fields.Many2One('currency.currency', 'Currency', required=True)
    contract_generator = fields.Many2One(
        'ir.sequence', 'Contract Number Generator',
        context={'code': 'ins_product.product'}, required=True,
        ondelete='RESTRICT')
    term_renewal_rules = fields.One2Many(
        'ins_product.term_renewal_rule', 'offered', 'Term - Renewal')
    item_descriptors = fields.Many2Many(
        'ins_product.product-item_desc',
        'product', 'item_desc', 'Item Descriptors',
        domain=[('id', 'in', Eval('possible_item_descs'))],
        depends=['possible_item_descs'], required=True)
    possible_item_descs = fields.Function(
        fields.Many2Many('ins_product.item_desc', None, None,
            'Possible Item Descriptors'),
        'get_possible_item_descs_id')
    complementary_data_def = fields.Many2Many(
        'ins_product.product-complementary_data_def',
        'product', 'complementary_data_def', 'Complementary Data',
        domain=[('kind', '=', 'contract')])
    # Temporary
    tmp_claim_manager = fields.Many2One(
        'party.party', 'Claim Manager', domain=[('is_company', '=', True)])
    tmp_contract_manager = fields.Many2One(
        'party.party', 'Contract Manager', domain=[('is_company', '=', True)])

    @classmethod
    def __setup__(cls):
        super(Product, cls).__setup__()
        cls._sql_constraints += [
            ('code_uniq', 'UNIQUE(code)', 'The code must be unique!'),
        ]

    @classmethod
    def delete(cls, entities):
        cls.delete_rules(entities)
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
            res = self.get_result('price', args, kind='pricing')
        except NonExistingRuleKindException:
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
            res = self.get_result('eligibility', args, kind='eligibility')
        except NonExistingRuleKindException:
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
            return self.get_result('frequency', args, kind='pricing')
        except NonExistingRuleKindException:
            pass
        for coverage in self.get_valid_options():
            try:
                return coverage.get_result(
                    'frequency', args, kind='pricing')
            except NonExistingRuleKindException:
                pass
        return 'yearly', []

    @staticmethod
    def default_currency():
        return business.get_default_currency()

    def give_me_step(self, args):
        good_family = self.give_me_families(args)[0][0]
        return good_family.get_step_model(args['step_name']), []

    def give_me_new_contract_number(self, args=None):
        return self.contract_generator.get_id(self.contract_generator.id)

    def give_me_complementary_data_ids_aggregate(self, args):
        if not 'dd_args' in args:
            return [], []
        res = set()
        errs = []
        for opt in self.options:
            result, errors = opt.get_result(
                'complementary_data_ids_aggregate',
                args)
            map(lambda x: res.add(x), result)
            errs += errors
        return list(res), errs

    def give_me_complementary_data_getter(self, args):
        if not 'dd_args' in args:
            return [], []
        dd_args = args['dd_args']
        if not 'path' in dd_args:
            if not 'options' in dd_args:
                return self.give_me_complementary_data_ids(args)
            dd_args['path'] = 'all'
        return self.give_me_complementary_data_ids_aggregate(args)

    def give_me_documents(self, args):
        if 'option' in args:
            for opt in self.options:
                if opt.code == args['option']:
                    return opt.give_me_documents(args)
        else:
            try:
                return self.get_result(
                    'documents', args, kind='document')
            except NonExistingRuleKindException:
                return [], ()
        return [], ()

    def get_currency(self):
        return self.currency

    def give_me_calculated_complementary_datas(self, args):
        # We prepare the call to the 'calculate_value_set' API.
        # It needs the following parameters:
        #  - The list of the schemas it must look for
        #  - The list of all the schemas in the tree. This list should
        #    contain all the schemas from the first list
        #  - All the values available for all relevent schemas
        if not 'contract' in args or not 'date' in args:
            raise Exception('Expected contract and date in args, got %s' % (
                str([k for k in args.iterkeys()])))
        all_schemas, possible_schemas = \
            self.get_complementary_data_for_execution(args)
        if not 'sub_elem' in args:
            for coverage in args['contract'].get_active_coverages_at_date(
                    args['date']):
                coverage_all, coverage_possible = \
                    coverage.get_complementary_data_for_execution(args)
                all_schemas |= coverage_all
                possible_schemas |= coverage_possible
        else:
            coverage = args['sub_elem'].get_coverage()
            coverage_all, coverage_possible = \
                coverage.get_complementary_data_for_execution(args)
            all_schemas |= coverage_all
            possible_schemas |= coverage_possible
        existing_data = {}
        if args['contract'].complementary_data:
            existing_data.update(args['contract'].complementary_data)
        if 'sub_elem' in args and args['sub_elem'].complementary_data:
            existing_data.update(args['sub_elem'].complementary_data)
        ComplementaryData = Pool().get('ins_product.complementary_data_def')
        result = ComplementaryData.calculate_value_set(
            possible_schemas, all_schemas, existing_data)
        return result, ()

    def get_possible_item_descs_id(self, name):
        res = []
        for option in self.options:
            if not utils.is_none(option, 'item_desc'):
                res.append(option.item_desc.id)
        return res


class ProductOptionsCoverage(model.CoopSQL):
    'Define Product - Coverage relations'

    __name__ = 'ins_product.product-options-coverage'

    product = fields.Many2One(
        'ins_product.product', 'Product',
        select=1, required=True, ondelete='CASCADE')
    coverage = fields.Many2One(
        'ins_product.coverage', 'Coverage',
        select=1, required=True, ondelete='RESTRICT')


class ProductDefinition(model.CoopView):
    'Product Definition'

    # This class is the base of Product Definitions. It defines number of
    # methods which will be used to define a business family behaviour in
    # the application

    def get_extension_model(self):
        raise NotImplementedError


class ItemDescriptor(model.CoopSQL, model.CoopView):
    'Item Descriptor'

    __name__ = 'ins_product.item_desc'

    code = fields.Char('Code', required=True, on_change_with=['name', 'code'])
    name = fields.Char('Name')
    complementary_data_def = fields.Many2Many(
        'ins_product.item_desc-complementary_data_def',
        'item_desc', 'complementary_data_def', 'Complementary Data',
        domain=[('kind', '=', 'sub_elem')], )
    kind = fields.Selection('get_possible_item_kind', 'Kind')
    parent = fields.Many2One('ins_product.item_desc', 'Parent')
    sub_item_descs = fields.One2Many('ins_product.item_desc', 'parent',
        'Sub Item Descriptors', states={'invisible': Eval('kind') == 'person'})

    def on_change_with_code(self):
        if self.code:
            return self.code
        elif self.name:
            return coop_string.remove_blank_and_invalid_char(self.name)

    @classmethod
    def get_possible_item_kind(cls):
        return [
            ('', ''),
            ('party', 'Party'),
            ('person', 'Person'),
            ('company', 'Company'),
        ]


class ItemDescriptorComplementaryDataRelation(model.CoopSQL):
    'Relation between Item Descriptor and Complementary Data'

    __name__ = 'ins_product.item_desc-complementary_data_def'

    item_desc = fields.Many2One(
        'ins_product.item_desc', 'Item Desc', ondelete='CASCADE', )
    complementary_data_def = fields.Many2One(
        'ins_product.complementary_data_def',
        'Complementary Data', ondelete='RESTRICT', )


class ProductItemDescriptorRelation(model.CoopSQL):
    'Relation between Product and Item Descriptor'

    __name__ = 'ins_product.product-item_desc'

    product = fields.Many2One(
        'ins_product.product', 'Product', ondelete='CASCADE')
    item_desc = fields.Many2One(
        'ins_product.item_desc', 'Item Descriptor', ondelete='RESTRICT')


class ProductComplementaryDataRelation(model.CoopSQL):
    'Relation between Product and Complementary Data'

    __name__ = 'ins_product.product-complementary_data_def'

    product = fields.Many2One(
        'ins_product.product', 'Product', ondelete='CASCADE')
    complementary_data_def = fields.Many2One(
        'ins_product.complementary_data_def',
        'Complementary Data', ondelete='RESTRICT')


class ExpenseKind(model.CoopSQL, model.CoopView):
    'Expense Kind'

    __name__ = 'ins_product.expense_kind'

    kind = fields.Selection(
        [
            ('medical', 'Medical'),
            ('expert', 'Expert'),
            ('judiciary', 'Judiciary'),
            ('other', 'Other'),
        ], 'Kind')
    code = fields.Char('Code', required=True)
    name = fields.Char('Name')
    short_name = fields.Char('Short Name')

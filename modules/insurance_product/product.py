#-*- coding:utf-8 -*-
import copy

from trytond.pool import PoolMeta
from trytond.pyson import Eval, Bool

from trytond.modules.coop_utils import model, utils, fields
from trytond.modules.coop_utils import coop_string
from trytond.modules.offered import NonExistingRuleKindException
from trytond.modules.insurance_product import PricingResultLine
from trytond.modules.insurance_product import EligibilityResultLine


__all__ = [
    'Offered',
    'Product',
    'OfferedProduct',
    'ItemDescriptor',
    'ItemDescriptorComplementaryDataRelation',
    'ProductItemDescriptorRelation',
    'ExpenseKind',
    ]

IS_INSURANCE = Eval('kind') == 'insurance'


class Offered():
    'Offered'

    __name__ = 'offered.offered'
    __metaclass__ = PoolMeta

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

    def get_name_for_billing(self):
        return self.name

    def get_good_rule_at_date(self, data, kind):
        # First we got to check that the fields that we will need to calculate
        # which rule is appliable are available in the data dictionnary
        try:
            the_date = data['appliable_conditions_date']
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


class Product():
    'Product'

    __name__ = 'offered.product'
    __metaclass__ = PoolMeta

    term_renewal_rules = fields.One2Many(
        'ins_product.term_renewal_rule', 'offered', 'Term - Renewal')
    item_descriptors = fields.Many2Many(
        'offered.product-item_desc',
        'product', 'item_desc', 'Item Descriptors',
        domain=[('id', 'in', Eval('possible_item_descs'))],
        depends=['possible_item_descs'],
        states={
            'required': IS_INSURANCE,
            'invisible': ~IS_INSURANCE,
            })
    possible_item_descs = fields.Function(
        fields.Many2Many('ins_product.item_desc', None, None,
            'Possible Item Descriptors', on_change_with=['coverages']),
        'on_change_with_possible_item_descs')

    @classmethod
    def __setup__(cls):
        super(Product, cls).__setup__()
        cls.kind = copy.copy(cls.kind)
        cls.kind.selection.append(('insurance', 'Insurance'))
        if ('default', 'Default') in cls.kind.selection:
            cls.kind.selection.remove(('default', 'Default'))
        cls.kind.selection = list(set(cls.kind.selection))

    @classmethod
    def delete(cls, entities):
        cls.delete_rules(entities)
        super(Product, cls).delete(entities)

    def get_sub_elem_data(self):
        # This method is used by the get_result method to know where to look
        # for sub-elements to parse and what fields can be used for key
        # matching
        #
        # Here it states that Product objects have a list of 'coverages' which
        # implements the GetResult class, and on which we might use 'code' or
        # 'name' as keys.
        return ('coverages', ['code', 'name'])

    def give_me_coverages_price(self, args):
        errs = []
        res = []
        self.init_dict_for_rule_engine(args)
        for coverage in self.get_valid_coverages():
            _res, _errs = coverage.get_result('price', args)
            if _res:
                res.extend(_res)
            errs += _errs
        return (res, errs)

    def give_me_product_price(self, args):
        # There is a pricing manager on the products so we can just forward the
        # request.
        try:
            res = self.get_result('price', args, kind='pricing')
        except NonExistingRuleKindException:
            return ([], [])
        if not res[0]:
            result_line = PricingResultLine()
            result_line.init_from_args(args)
            result_line.on_object = self
            return ([result_line], res[1])
        return [res[0]], res[1]

    def give_me_total_price(self, args):
        # Total price is the sum of coverages price and Product price
        (p_price, errs_product) = self.give_me_product_price(args)
        (o_price, errs_coverages) = self.give_me_coverages_price(args)

        lines = p_price + o_price
        # lines = []
        # for line in p_price + o_price:
            # if line.value == 0:
                # continue
            # lines.append(line)

        return (lines, errs_product + errs_coverages)

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
        for coverage in self.get_valid_coverages():
            res, errs = coverage.get_result('family', args)
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
        for coverage in self.get_valid_coverages():
            try:
                return coverage.get_result(
                    'frequency', args, kind='pricing')
            except NonExistingRuleKindException:
                pass
        return 'yearly', []

    def give_me_documents(self, args):
        if 'option' in args:
            for coverage in self.coverages:
                if coverage.code == args['option']:
                    return coverage.give_me_documents(args)
        else:
            try:
                return self.get_result(
                    'documents', args, kind='document')
            except NonExistingRuleKindException:
                return [], ()
        return [], ()

    def on_change_with_possible_item_descs(self, name=None):
        res = []
        for coverage in self.coverages:
            if not utils.is_none(coverage, 'item_desc'):
                res.append(coverage.item_desc.id)
        return res

    def get_cmpl_data_looking_for_what(self, args):
        if 'sub_elem' in args and args['level'] == 'covered_data':
            return ''
        return super(Product, self).get_cmpl_data_looking_for_what(args)


class OfferedProduct(Offered):
    'Offered Product'

    __name__ = 'offered.product'
    #This empty override is necessary to have in the product, the fields added
    #in the override of offered


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
    def _export_force_recreate(cls):
        result = super(ItemDescriptor, cls)._export_force_recreate()
        result.remove('sub_item_descs')
        return result

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
        'offered.complementary_data_def',
        'Complementary Data', ondelete='RESTRICT', )


class ProductItemDescriptorRelation(model.CoopSQL):
    'Relation between Product and Item Descriptor'

    __name__ = 'offered.product-item_desc'

    product = fields.Many2One(
        'offered.product', 'Product', ondelete='CASCADE')
    item_desc = fields.Many2One(
        'ins_product.item_desc', 'Item Descriptor', ondelete='RESTRICT')


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

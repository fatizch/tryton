#-*- coding:utf-8 -*-
from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.cog_utils import model, utils, fields, coop_date
from trytond.modules.cog_utils import coop_string

from trytond.modules.offered import NonExistingRuleKindException
from trytond.modules.offered import PricingResultLine
from trytond.modules.offered import EligibilityResultLine


__metaclass__ = PoolMeta
__all__ = [
    'Offered',
    'Product',
    'OfferedProduct',
    'ItemDescription',
    'ItemDescSubItemDescRelation',
    'ItemDescriptionExtraDataRelation',
    'ProductItemDescriptionRelation',
    ]

IS_INSURANCE = Eval('kind') == 'insurance'


class Offered:
    __name__ = 'offered'

    premium_rules = fields.One2Many('billing.premium.rule', 'offered',
        'Premium Rules')
    eligibility_rules = fields.One2Many('offered.eligibility.rule', 'offered',
        'Eligibility Rules')
    clause_rules = fields.One2Many('clause.rule', 'offered', 'Clause Rules')
    deductible_rules = fields.One2Many('offered.deductible.rule', 'offered',
        'Deductible Rules')
    document_rules = fields.One2ManyDomain('document.rule', 'offered',
        'Document Rules', context={'doc_rule_kind': 'main'},
        domain=[('kind', '=', 'main')])
    sub_document_rules = fields.One2ManyDomain('document.rule', 'offered',
        'Sub Document Rules', context={'doc_rule_kind': 'sub'},
        domain=[('kind', '=', 'sub')])

    def get_name_for_billing(self):
        return self.name

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
            res = self.get_result('sub_elem_eligibility', args,
                kind='eligibility')
        except NonExistingRuleKindException:
            return (EligibilityResultLine(True), [])
        return res

    def give_me_documents(self, args):
        try:
            return self.get_result('documents', args, kind='document')
        except NonExistingRuleKindException:
            return [], ()

    def give_me_all_clauses(self, args):
        try:
            return self.get_result('all_clauses', args, kind='clause')
        except NonExistingRuleKindException:
            return [], ()


class Product:
    __name__ = 'offered.product'

    term_renewal_rules = fields.One2Many('offered.term.rule', 'offered',
        'Term - Renewal')
    item_descriptors = fields.Many2Many('offered.product-item.description',
        'product', 'item_desc', 'Item Descriptions',
        depends=['possible_item_descs'], states={
            'required': IS_INSURANCE,
            'invisible': ~IS_INSURANCE,
            })
    possible_item_descs = fields.Function(
        fields.Many2Many('offered.item.description', None, None,
            'Possible Item Descriptions', on_change_with=['coverages']),
        'on_change_with_possible_item_descs')

    @classmethod
    def __setup__(cls):
        super(Product, cls).__setup__()
        cls._error_messages.update({
                'no_renewal_rule_configured': 'No renewal rule configured',
                })

    @classmethod
    def delete(cls, entities):
        cls.delete_rules(entities)
        super(Product, cls).delete(entities)

    @classmethod
    def get_possible_product_kind(cls):
        res = super(Product, cls).get_possible_product_kind()
        res.append(('insurance', 'Insurance'))
        return res

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
        self.init_dict_for_rule_engine(args)
        result_line = PricingResultLine(on_object=self)
        result_line.init_from_args(args)
        try:
            product_line, product_errs = self.get_result('price', args,
                kind='premium')
        except NonExistingRuleKindException:
            product_line = None
            product_errs = []
        if product_line and product_line.amount:
            product_line.on_object = args['contract']
            result_line.add_detail_from_line(product_line)
        return [result_line] if result_line.amount else [], product_errs

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
            return self.get_result('frequency', args, kind='premium')
        except NonExistingRuleKindException:
            pass
        for coverage in self.get_valid_coverages():
            try:
                return coverage.get_result(
                    'frequency', args, kind='premium')
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

    def give_me_next_renewal_date(self, args):
        try:
            return self.get_result('next_renewal_date', args,
                kind='term_renewal')
        except NonExistingRuleKindException:
            return None, [('no_renewal_rule_configured', ())]

    @classmethod
    def get_var_names_for_full_extract(cls):
        res = super(Product, cls).get_var_names_for_full_extract()
        res.extend(['item_descriptors'])
        return res

    def get_contract_dates(self, dates, contract):
        super(Product, self).get_contract_dates(dates, contract)
        if (hasattr(contract, 'last_renewed') and contract.last_renewed):
            dates.add(contract.last_renewed)

    def get_covered_data_dates(self, dates, covered_data):
        dates.add(covered_data.start_date)
        if hasattr(covered_data, 'end_date') and covered_data.end_date:
            dates.add(coop_date.add_day(covered_data.end_date, 1))

    def get_covered_element_dates(self, dates, covered_element):
        for data in covered_element.covered_data:
            self.get_covered_data_dates(dates, data)
        if hasattr(covered_element, 'sub_covered_elements'):
            for sub_elem in covered_element.sub_covered_elements:
                self.get_covered_element_dates(dates, sub_elem)

    def get_dates(self, contract):
        dates = super(Product, self).get_dates(contract)
        for covered in contract.covered_elements:
            self.get_covered_element_dates(dates, covered)
        return dates


class OfferedProduct(Offered):
    'Offered Product'

    __name__ = 'offered.product'
    #This empty override is necessary to have in the product, the fields added
    #in the override of offered


class ItemDescription(model.CoopSQL, model.CoopView):
    'Item Description'

    __name__ = 'offered.item.description'

    code = fields.Char('Code', required=True, on_change_with=['name', 'code'])
    name = fields.Char('Name')
    extra_data_def = fields.Many2Many(
        'offered.item.description-extra_data',
        'item_desc', 'extra_data_def', 'Extra Data',
        domain=[('kind', '=', 'sub_elem')], )
    kind = fields.Selection([
            ('', ''),
            ('party', 'Party'),
            ('person', 'Person'),
            ('company', 'Company'),
            ], 'Kind')
    sub_item_descs = fields.Many2Many(
        'offered.item.description-sub_item.description',
        'item_desc', 'sub_item_desc', 'Sub Item Descriptions',
        states={'invisible': Eval('kind') == 'person'})

    def on_change_with_code(self):
        if self.code:
            return self.code
        elif self.name:
            return coop_string.remove_blank_and_invalid_char(self.name)

    # @classmethod
    # def _export_force_recreate(cls):
    #     result = super(ItemDescription, cls)._export_force_recreate()
    #     result.remove('sub_item_descs')
    #     return result

    @classmethod
    def get_var_names_for_full_extract(cls):
        res = super(ItemDescription, cls).get_var_names_for_full_extract()
        res.extend(['extra_data_def', 'kind', 'sub_item_descs'])
        return res


class ItemDescSubItemDescRelation(model.CoopSQL):
    'Relation between Item Desc and Sub Item Desc'

    __name__ = 'offered.item.description-sub_item.description'

    item_desc = fields.Many2One('offered.item.description', 'Item Desc',
        ondelete='CASCADE')
    sub_item_desc = fields.Many2One('offered.item.description',
        'Sub Item Desc', ondelete='RESTRICT')


class ItemDescriptionExtraDataRelation(model.CoopSQL):
    'Item Description to Extra Data Relation'

    __name__ = 'offered.item.description-extra_data'

    item_desc = fields.Many2One('offered.item.description', 'Item Desc',
        ondelete='CASCADE')
    extra_data_def = fields.Many2One('extra_data', 'Extra Data',
        ondelete='RESTRICT', )


class ProductItemDescriptionRelation(model.CoopSQL):
    'Relation between Product and Item Description'

    __name__ = 'offered.product-item.description'

    product = fields.Many2One('offered.product', 'Product', ondelete='CASCADE')
    item_desc = fields.Many2One('offered.item.description', 'Item Description',
        ondelete='RESTRICT')

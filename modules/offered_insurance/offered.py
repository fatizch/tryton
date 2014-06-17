#-*- coding:utf-8 -*-
from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.cog_utils import model, utils, fields, coop_date
from trytond.modules.cog_utils import coop_string

from trytond.modules.offered import NonExistingRuleKindException
from trytond.modules.offered import EligibilityResultLine


__metaclass__ = PoolMeta
__all__ = [
    'Offered',
    'Product',
    'OfferedProduct',
    'ItemDescription',
    'ItemDescSubItemDescRelation',
    'ItemDescriptionExtraDataRelation',
    ]

IS_INSURANCE = Eval('kind') == 'insurance'


class Offered:
    __name__ = 'offered'

    premium_rules = fields.One2Many('billing.premium.rule', 'offered',
        'Premium Rules')
    eligibility_rules = fields.One2Many('offered.eligibility.rule', 'offered',
        'Eligibility Rules')
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


class Product:
    __name__ = 'offered.product'

    term_renewal_rules = fields.One2Many('offered.term.rule', 'offered',
        'Term - Renewal')
    item_descriptors = fields.Function(
        fields.Many2Many('offered.item.description', None, None,
            'Item Descriptions'),
        'on_change_with_item_descriptors')

    @classmethod
    def __setup__(cls):
        super(Product, cls).__setup__()
        cls.extra_data_def.domain = [
            ('kind', 'in', ['contract', 'covered_element', 'option'])]
        cls._error_messages.update({
                'no_renewal_rule_configured': 'No renewal rule configured',
                'missing_covered_element_extra_data': 'The following covered '
                'element extra data should be set on the product: %s',
                })

    @classmethod
    def validate(cls, instances):
        super(Product, cls).validate(instances)
        cls.validate_covered_element_extra_data(instances)

    @classmethod
    def validate_covered_element_extra_data(cls, instances):
        for instance in instances:
            from_option = set(extra_data for coverage in instance.coverages
                for extra_data in coverage.extra_data_def
                if extra_data.kind == 'covered_element')
            remaining = from_option - set(instance.extra_data_def)
            if remaining:
                instance.raise_user_error('missing_covered_element_extra_data',
                    (', '.join((extra_data.string
                                for extra_data in remaining))))

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
                res += _res
            errs += _errs
        return res, errs

    def give_me_product_price(self, args):
        # There is a pricing manager on the products so we can just forward the
        # request.
        self.init_dict_for_rule_engine(args)
        try:
            product_lines, product_errs = self.get_result('price', args,
                kind='premium')
        except NonExistingRuleKindException:
            product_lines = []
            product_errs = []
        return product_lines, product_errs

    def give_me_total_price(self, args):
        # Total price is the sum of coverages price and Product price
        p_price, errs_product = self.give_me_product_price(args)
        o_price, errs_coverages = self.give_me_coverages_price(args)

        return (p_price + o_price, errs_product + errs_coverages)

    def give_me_families(self, args):
        self.update_args(args)
        result = []
        errors = []
        for coverage in self.get_valid_coverages():
            result.append(coverage.family)
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

    @fields.depends('coverages')
    def on_change_with_item_descriptors(self, name=None):
        res = set()
        for coverage in self.coverages:
            if getattr(coverage, 'item_desc', None):
                res.add(coverage.item_desc.id)
        return list(res)

    def get_cmpl_data_looking_for_what(self, args):
        if 'elem' in args and args['level'] == 'option':
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
        if contract.next_renewal_date:
            dates.add(contract.next_renewal_date)
            if not contract.end_date:
                return
            # Calculate every anniversary date until contrat termination
            cur_date = contract.next_renewal_date
            while cur_date <= contract.end_date:
                dates.add(cur_date)
                cur_date = coop_date.add_year(cur_date, 1)
        return dates

    def get_option_dates(self, dates, option):
        super(Product, self).get_option_dates(dates, option)
        if (hasattr(option, 'extra_premiums') and
                option.extra_premiums):
            for elem in option.extra_premiums:
                dates.add(elem.start_date)

    def get_covered_element_dates(self, dates, covered_element):
        for data in covered_element.options:
            self.get_option_dates(dates, data)
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

    code = fields.Char('Code', required=True)
    name = fields.Char('Name')
    extra_data_def = fields.Many2Many(
        'offered.item.description-extra_data',
        'item_desc', 'extra_data_def', 'Extra Data',
        domain=[('kind', '=', 'covered_element')], )
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
    coverages = fields.One2Many('offered.option.description', 'item_desc',
        'Coverages')

    @fields.depends('name', 'code')
    def on_change_with_code(self):
        if self.code:
            return self.code
        elif self.name:
            return coop_string.remove_blank_and_invalid_char(self.name)

    @classmethod
    def get_var_names_for_full_extract(cls):
        res = super(ItemDescription, cls).get_var_names_for_full_extract()
        res.extend(['extra_data_def', 'kind', 'sub_item_descs'])
        return res

    @classmethod
    def _export_skips(cls):
        result = super(ItemDescription, cls)._export_skips()
        result.add('coverages')
        return result


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

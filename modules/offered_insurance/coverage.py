# -*- coding:utf-8 -*-
import copy
import datetime

from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.cog_utils import utils, fields
from trytond.modules.offered_insurance import offered
from trytond.modules.offered import EligibilityResultLine


__metaclass__ = PoolMeta
__all__ = [
    'OptionDescription',
    'OfferedOptionDescription',
    ]

COULD_NOT_FIND_A_MATCHING_RULE = 'Could not find a matching rule'


class OptionDescription:
    __name__ = 'offered.option.description'

    insurance_kind = fields.Selection([('', '')], 'Insurance Kind',
        states={'invisible': Eval('kind') != 'insurance'}, sort=False,
        depends=['kind'])
    insurer = fields.Many2One('insurer', 'Insurer',
        states={'invisible': ~offered.IS_INSURANCE}, ondelete='RESTRICT')
    family = fields.Selection([('generic', 'Generic')], 'Family',
        states={
            'invisible': ~offered.IS_INSURANCE,
            'required': offered.IS_INSURANCE,
            })
    item_desc = fields.Many2One('offered.item.description', 'Item Description',
        ondelete='RESTRICT', states={'required': ~Eval('is_service')},
        depends=['is_service'])

    @classmethod
    def __setup__(cls):
        super(OptionDescription, cls).__setup__()
        cls.extra_data_def.domain = [
            ('kind', 'in', ['contract', 'covered_element', 'option'])]
        for field_name in (mgr for mgr in dir(cls) if mgr.endswith('_mgr')):
            cur_attr = copy.copy(getattr(cls, field_name))
            if not hasattr(cur_attr, 'context') or not isinstance(
                    cur_attr, fields.Field):
                continue
            if cur_attr.context is None:
                cur_attr.context = {}
            # cur_attr.context['for_family'] = Eval('family')
            cur_attr = copy.copy(cur_attr)
            setattr(cls, field_name, cur_attr)

    @classmethod
    def _export_light(cls):
        return (super(OptionDescription, cls)._export_light() |
            set(['insurer']))

    @classmethod
    def default_family(cls):
        return 'generic'

    @staticmethod
    def default_insurance_kind():
        return ''

    @fields.depends('item_desc')
    def on_change_with_is_service(self, name=None):
        return not self.item_desc

    @fields.depends('is_service')
    def on_change_with_item_desc(self):
        if self.is_service:
            return None

    @classmethod
    def delete(cls, entities):
        cls.delete_rules(entities)
        super(OptionDescription, cls).delete(entities)

    @classmethod
    def get_possible_option_description_kind(cls):
        res = super(OptionDescription,
            cls).get_possible_option_description_kind()
        res.append(('insurance', 'Insurance'))
        return res

    @classmethod
    def get_possible_coverages_clause(cls, instance, at_date):
        clause = super(OptionDescription, cls).get_possible_coverages_clause(
            instance, at_date)
        if instance and instance.__name__ == 'contract.covered_element':
            return clause + [
                ('products', '=', instance.product.id),
                ('item_desc', '=', instance.item_desc.id)]
        return clause

    def calculate_main_price(self, args, errs, date, contract):
        try:
            coverage_lines, coverage_errs = self.get_result(
                'price', args, kind='premium')
        except offered.NonExistingRuleKindException:
            coverage_lines = []
            coverage_errs = []
        errs += coverage_errs
        return coverage_lines

    def calculate_sub_elem_price(self, args, errs):
        lines, errs = [], []
        for covered, option in self.give_me_covered_elements_at_date(
                args)[0]:
            tmp_args = args.copy()
            option.init_dict_for_rule_engine(tmp_args)
            try:
                sub_elem_lines, sub_elem_errs = self.get_result(
                    'sub_elem_price', tmp_args, kind='premium')
            except offered.NonExistingRuleKindException:
                sub_elem_lines = []
                sub_elem_errs = []
            errs += sub_elem_errs
            lines += sub_elem_lines
        return lines

    def give_me_price(self, args):
        data_dict, errs = utils.get_data_from_dict(['contract', 'date'], args)
        if errs:
            return ([], errs)
        contract = data_dict['contract']
        date = data_dict['date']
        result = []
        result += self.calculate_main_price(args, errs, date, contract)
        result += self.calculate_sub_elem_price(args, errs)

        return (result, errs)

    def give_me_eligibility(self, args):
        try:
            res = self.get_result('eligibility', args, kind='eligibility')
        except offered.NonExistingRuleKindException:
            return (EligibilityResultLine(True), [])
        return res

    def give_me_covered_elements_at_date(self, args):
        contract = args['contract']
        res = []
        for covered in contract.covered_elements:
            for option in covered.options:
                if option.coverage != self:
                    continue
                if not(option.start_date <= args['date']
                        <= (option.end_date or datetime.date.max)):
                    continue
                if option.status in ('quote', 'active'):
                    res.append((covered, option))
        return res, []

    def give_me_allowed_amounts(self, args):
        try:
            return self.get_result(
                'allowed_amounts',
                args,
                kind='coverage_amount')
        except offered.NonExistingRuleKindException:
            return [], []

    def give_me_documents(self, args):
        try:
            if 'kind' in args and args['kind'] == 'sub':
                res, errs = self.get_result(
                    'documents', args, kind='sub_document')
            else:
                res, errs = self.get_result('documents', args, kind='document')
        except offered.NonExistingRuleKindException:
            return [], []

        return res, errs

    def give_me_must_have_coverage_amount(self, args):
        result = self.get_good_rule_at_date(args, 'coverage_amount')

        if not result:
            return False, []
        return True, []

    def give_me_coverage_amount_validity(self, args):
        try:
            return self.get_result(
                'coverage_amount_validity',
                args,
                kind='coverage_amount')
        except offered.NonExistingRuleKindException:
            return (True, []), []

    def give_me_dependant_amount_coverage(self, args):
        try:
            return self.get_result(
                'dependant_amount_coverage',
                args,
                kind='coverage_amount')
        except offered.NonExistingRuleKindException:
            return None, []

    def get_currency(self):
        return self.currency

    @classmethod
    def get_var_names_for_full_extract(cls):
        res = super(OptionDescription, cls).get_var_names_for_full_extract()
        res.extend([('item_desc', 'light')])
        return res


class OfferedOptionDescription(offered.Offered):
    'OptionDescription'

    __name__ = 'offered.option.description'
    # This empty override is necessary to have in the coverage the fields added
    # in the override of offered

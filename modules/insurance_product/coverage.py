#-*- coding:utf-8 -*-
import copy

from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, Or, And

from trytond.modules.coop_utils import utils, fields
from trytond.modules.insurance_product import product
from trytond.modules.insurance_product import PricingResultLine
from trytond.modules.insurance_product import EligibilityResultLine
from .product import IS_INSURANCE


__all__ = [
    'Coverage',
    'OfferedCoverage',
]

COULD_NOT_FIND_A_MATCHING_RULE = 'Could not find a matching rule'


class Coverage():
    'Coverage'

    __name__ = 'offered.coverage'
    __metaclass__ = PoolMeta

    benefits = fields.Many2Many('offered.coverage-benefit', 'coverage',
        'benefit', 'Benefits', context={
            'start_date': Eval('start_date'),
            'currency_digits': Eval('currency_digits')},
        states={
            'readonly': ~Eval('start_date'),
            'invisible': Or(~~Eval('is_package'), ~IS_INSURANCE),
            }, depends=['currency_digits'])
    insurer = fields.Many2One('party.insurer', 'Insurer', states={
            'invisible': Or(~~Eval('is_package'), ~IS_INSURANCE)
            }, depends=['is_package'])
    family = fields.Selection([('', '')], 'Family', states={
            'invisible': Or(~~Eval('is_package'), ~IS_INSURANCE),
            'required': And(~Eval('is_package'), IS_INSURANCE),
            }, depends=['is_package'])
    item_desc = fields.Many2One('ins_product.item_desc', 'Item Descriptor',
        states={
            'invisible': Or(~~Eval('is_package'), ~IS_INSURANCE),
            'required': And(~Eval('is_package'), IS_INSURANCE),
            }, depends=['is_package'])

    @classmethod
    def __setup__(cls):
        super(Coverage, cls).__setup__()
        for field_name in (mgr for mgr in dir(cls) if mgr.endswith('_mgr')):
            cur_attr = copy.copy(getattr(cls, field_name))
            if not hasattr(cur_attr, 'context') or not isinstance(
                    cur_attr, fields.Field):
                continue
            if cur_attr.context is None:
                cur_attr.context = {}
            #cur_attr.context['for_family'] = Eval('family')
            cur_attr = copy.copy(cur_attr)
            setattr(cls, field_name, cur_attr)

        cls.kind = copy.copy(cls.kind)
        cls.kind.selection.append(('insurance', 'Insurance'))
        if ('default', 'Default') in cls.kind.selection:
            cls.kind.selection.remove(('default', 'Default'))
        cls.kind.selection = list(set(cls.kind.selection))

    @classmethod
    def delete(cls, entities):
        cls.delete_rules(entities)
        super(Coverage, cls).delete(entities)

    def give_me_price(self, args):
        data_dict, errs = utils.get_data_from_dict(['contract', 'date'], args)
        if errs:
            return ([], errs)
        contract = data_dict['contract']
        date = data_dict['date']

        active_coverages = contract.get_active_coverages_at_date(date)
        if not self in active_coverages:
            return (None, [])

        result_line = PricingResultLine(on_object=self)
        result_line.init_from_args(args)
        try:
            coverage_line, coverage_errs = self.get_result(
                'price', args, kind='pricing')
        except product.NonExistingRuleKindException:
            coverage_line = None
            coverage_errs = []
        if coverage_line and coverage_line.amount:
            for_option = contract.get_option_for_coverage_at_date(
                self, date)
            if for_option:
                coverage_line.on_object = for_option
            result_line.add_detail_from_line(coverage_line)
        errs += coverage_errs

        for covered, covered_data in self.give_me_covered_elements_at_date(
                args)[0]:
            tmp_args = args
            tmp_args['sub_elem'] = covered
            tmp_args['data'] = covered_data
            try:
                sub_elem_line, sub_elem_errs = self.get_result(
                    'sub_elem_price', tmp_args, kind='pricing')
            except product.NonExistingRuleKindException:
                sub_elem_line = None
                sub_elem_errs = []
            if sub_elem_line and sub_elem_line.amount:
                sub_elem_line.on_object = covered_data
                result_line.add_detail_from_line(sub_elem_line)
            errs += sub_elem_errs
        return ([result_line], errs)

    def get_dates(self, dates=None, start=None, end=None):
        # This is a temporary functionality that is provided to ease the
        # checking of the pricing calculations.
        # In 'real life', it is not systematic to update the pricing when a new
        # version of the rule is defined
        if dates:
            res = set(dates)
        else:
            res = set()
        for rule in self.pricing_rules:
            res.add(rule.start_date)
        return utils.limit_dates(res, start, end)

    def give_me_eligibility(self, args):
        try:
            res = self.get_result('eligibility', args, kind='eligibility')
        except product.NonExistingRuleKindException:
            return (EligibilityResultLine(True), [])
        return res

    def give_me_family(self, args):
        return (Pool().get(self.family), [])

    def give_me_covered_elements_at_date(self, args):
        contract = args['contract']
        date = args['date']
        res = []
        for covered in contract.covered_elements:
            # We must check that the current covered element is
            # covered by self.
            for covered_data in covered.covered_data:
                coverage = utils.convert_ref_to_obj(
                    covered_data.option.offered)
                if not coverage.code == self.code:
                    continue

                # And that this coverage is effective at the requested
                # computation date.
                if (date >= covered_data.start_date and
                        (not covered_data.end_date
                            or covered_data.end_date >= date)):
                    res.append((covered, covered_data))
        return res, []

    def give_me_allowed_amounts(self, args):
        try:
            return self.get_result(
                'allowed_amounts',
                args,
                kind='coverage_amount')
        except product.NonExistingRuleKindException:
            return [], []

    def give_me_documents(self, args):
        try:
            if 'kind' in args and args['kind'] == 'sub':
                res, errs = self.get_result(
                    'documents', args, kind='sub_document')
            else:
                res, errs = self.get_result('documents', args, kind='document')
        except product.NonExistingRuleKindException:
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
        except product.NonExistingRuleKindException:
            return (True, []), []

    def get_currency(self):
        return self.currency


class OfferedCoverage(product.Offered):
    'Offered Coverage'

    __name__ = 'offered.coverage'
    #This empty override is necessary to have in the coverage the fields added
    #in the override of offered

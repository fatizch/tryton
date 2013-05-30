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
        # This method is one of the core of the pricing system. It asks for the
        # price for the self depending on the contrat that is given as an
        # argument.
        data_dict, errs = utils.get_data_from_dict(['contract', 'date'], args)
        if errs:
            # No contract means no price.
            return (None, errs)
        contract = data_dict['contract']
        date = data_dict['date']

        # We need to check that self is part of the subscribed coverages of the
        # contract.
        coverages = contract.get_active_coverages_at_date(date)
        res = PricingResultLine(name=self.name)
        res.on_object = utils.convert_to_reference(self)
        if self in coverages:
            # The first part of the pricing is the price at the coverage level.
            # It is computed by the pricing manager, so we just need to forward
            # the request.
            try:
                _res, _errs = self.get_result('price', args, kind='pricing')
            except product.NonExistingRuleKindException:
                _res = None
                _errs = []
            if _res and _res.value:
                # If a result exists, we give it a name and add it to the main
                # result
                for_option = contract.get_option_for_coverage_at_date(
                    self, date)
                if for_option:
                    if for_option.id:
                        _res.on_object = '%s,%s' % (
                            for_option.__name__, for_option.id)
                    else:
                        _res.name = 'Global Price'
                res += _res
                res.on_object = '%s,%s' % (
                    self.__name__, self.id)
            # We always append the errors (if any).
            errs += _errs

            # Now it is time to price the covered elements of the contract.
            # Note that they might have a role in the Base Price computation,
            # depending on the algorithm that is used.
            #
            # What we compute now is the part of the price that is associated
            # to each of the covered elements at the given date
            for covered, covered_data in self.give_me_covered_elements_at_date(
                    args)[0]:
                # Now we need to set a new argument before forwarding
                # the request to the manager, which is the covered
                # element it must work on.
                tmp_args = args
                tmp_args['sub_elem'] = covered
                tmp_args['data'] = covered_data

                # And we finally call the manager for the price
                try:
                    _res, _errs = self.get_result(
                        'sub_elem_price',
                        tmp_args,
                        kind='pricing')
                except product.NonExistingRuleKindException:
                    _res = None
                    _errs = []
                if _res and _res.value:
                    # Basically we set name = covered.product_specific
                    # .person.name, but 'product_specific' is a
                    # Reference field and is not automatically turned
                    # into a browse object.
                    # Should be done later by tryton.
                    _res.name = covered.get_name_for_info()
                    if covered_data.id:
                        _res.on_object = '%s,%s' % (
                            covered_data.__name__,
                            covered_data.id)
                    res += _res
                errs += _errs
            errs = list(set(errs))
            if COULD_NOT_FIND_A_MATCHING_RULE in errs:
                errs.remove(COULD_NOT_FIND_A_MATCHING_RULE)
            return (res, list(set(errs)))
        return (None, [])

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
        return res

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
                if not (date >= covered_data.start_date and
                        (not hasattr(covered_data, 'end_date') or
                            covered_data.end_date is None or
                            covered_data.end_date < date)):
                    continue
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

#-*- coding:utf-8 -*-
import copy

from trytond.model import fields
from trytond.pool import Pool
from trytond.pyson import Eval, Bool

from trytond.modules.coop_utils import model, business, utils
from trytond.modules.insurance_product import Offered
from trytond.modules.insurance_product import PricingResultLine
from trytond.modules.insurance_product import EligibilityResultLine


__all__ = [
    'Coverage',
    'PackageCoverage',
    ]

SUBSCRIPTION_BEHAVIOUR = [
    ('mandatory', 'Mandatory'),
    ('proposed', 'Proposed'),
    ('optional', 'Optional'),
]


class Coverage(model.CoopSQL, Offered):
    'Coverage'

    __name__ = 'ins_product.coverage'
    _export_name = 'code'

    insurer = fields.Many2One('party.insurer', 'Insurer',
        states={
            'invisible': Bool(Eval('is_package')),
        },
        depends=['is_package'])
    family = fields.Selection([('default', 'default')], 'Family',
        states={
            'invisible': Bool(Eval('is_package')),
            'required': Bool(~Eval('is_package')),
        },
        depends=['is_package'])
    benefits = fields.One2Many('ins_product.benefit', 'coverage', 'Benefits',
        context={
            'start_date': Eval('start_date'),
            'currency_digits': Eval('currency_digits'),
        },
        states={
            'readonly': ~Bool(Eval('start_date')),
            'invisible': Bool(Eval('is_package')),
        },
        depends=['currency_digits'])
    currency = fields.Many2One('currency.currency', 'Currency', required=True)
    coverage_amount_rules = fields.One2Many(
        'ins_product.coverage_amount_rule',
        'offered', 'Coverage Amount Rules',
        states={
            'invisible': Bool(Eval('is_package')),
        },)
    covered_dynamic_data_manager = model.One2ManyDomain(
        'ins_product.dynamic_data_manager',
        'master',
        'Covered Complementary Data Manager',
        context={
            'for_kind': 'sub_elem',
            'schema_element_kind': 'sub_elem',
        },
        domain=[('kind', '=', 'sub_elem')],
        size=1)
    subscription_behaviour = fields.Selection(SUBSCRIPTION_BEHAVIOUR,
        'Subscription Behaviour', sort=False)
    is_package = fields.Boolean('Package')
    coverages_in_package = fields.Many2Many('ins_product.package-coverage',
        'package', 'coverage', 'Coverages In Package',
        states={
            'invisible': Bool(~Eval('is_package')),
        },
        depends=['is_package'],
        domain=[('is_package', '=', False)])

    @classmethod
    def delete(cls, entities):
        cls.delete_rules(entities)
        utils.delete_reference_backref(
            entities,
            'ins_product.dynamic_data_manager',
            'master')
        super(Coverage, cls).delete(entities)

    @classmethod
    def __setup__(cls):
        super(Coverage, cls).__setup__()
        #Temporary remove, while impossible to duplicate whith same code
#        cls._sql_constraints += [
#            ('code_uniq', 'UNIQUE(code)', 'The code must be unique!'),
#        ]
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

        cls.template = copy.copy(cls.template)
        if not cls.template.domain:
            cls.template.domain = []
        cls.template.domain.append(('is_package', '=', Eval('is_package')))
        if not cls.template.depends:
            cls.template = []
        cls.template.depends.append('is_package')

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
        if self in coverages:
            # The first part of the pricing is the price at the coverage level.
            # It is computed by the pricing manager, so we just need to forward
            # the request.
            try:
                _res, _errs = self.get_result('price', args, kind='pricing')
            except utils.NonExistingRuleKindException:
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
                except utils.NonExistingRuleKindException:
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
            if utils.COULD_NOT_FIND_A_MATCHING_RULE in errs:
                errs.remove(utils.COULD_NOT_FIND_A_MATCHING_RULE)
            return (res, list(set(errs)))
        return (None, [])

    def get_dates(self):
        # This is a temporary functionnality that is provided to ease the
        # checking of the pricing calculations.
        # In 'real life', it is not systematic to update the pricing when a new
        # version of the rule is defined.
        res = set()
        for rule in self.pricing_rules:
            res.add(rule.start_date)
        return res

    def give_me_eligibility(self, args):
        try:
            res = self.get_result('eligibility', args, kind='eligibility')
        except utils.NonExistingRuleKindException:
            return (EligibilityResultLine(True), [])
        return res

    def give_me_sub_elem_eligibility(self, args):
        try:
            res = self.get_result(
                'sub_elem_eligibility', args, kind='eligibility')
        except utils.NonExistingRuleKindException:
            return (EligibilityResultLine(True), [])
        return res

    @staticmethod
    def default_currency():
        return business.get_default_currency()

    def give_me_family(self, args):
        return (Pool().get(self.family), [])

    def give_me_extension_field(self, args):
        return self.give_me_family(args)[0].get_extension_model()

    def give_me_covered_elements_at_date(self, args):
        contract = args['contract']
        date = args['date']
        res = []
        good_ext = self.give_me_extension_field(args)
        if not good_ext or not hasattr(contract, good_ext):
            return [], ['Extension not found']
        for covered in getattr(contract, good_ext)[0].covered_elements:
            # We must check that the current covered element is
            # covered by self.
            for covered_data in covered.covered_data:
                for_coverage = utils.convert_ref_to_obj(
                    covered_data.for_coverage)
                if not for_coverage.code == self.code:
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

    def is_valid(self):
        if self.template_behaviour == 'remove':
            return False
        return True

    def give_me_allowed_amounts(self, args):
        try:
            return self.get_result(
                'allowed_amounts',
                args,
                kind='coverage_amount')
        except utils.NonExistingRuleKindException:
            return [], []

    def give_me_coverage_amount_validity(self, args):
        try:
            return self.get_result(
                'coverage_amount_validity',
                args,
                kind='coverage_amount')
        except utils.NonExistingRuleKindException:
            return (True, []), []

    def give_me_dynamic_data_ids_aggregate(self, args):
        if not 'dd_args' in args:
            return [], []
        dd_args = args['dd_args']
        if not self.give_me_family(args)[0].get_extension_model() \
                == dd_args['path'] and not dd_args['path'] == 'all':
            return [], []
        if not('options' in dd_args and dd_args['options'] != '' and
                self.code in dd_args['options'].split(';')):
            return [], []
        if dd_args['kind'] == 'main':
            return self.give_me_dynamic_data_ids(args)
        elif dd_args['kind'] == 'sub_elem':
            return self.give_me_covered_dynamic_data_ids(args)
        return [], []

    def give_me_covered_dynamic_data_ids(self, args):
        if not(hasattr(self,
                'covered_dynamic_data_manager') and
                self.covered_dynamic_data_manager):
            return []
        return self.covered_dynamic_data_manager[0].get_valid_schemas_ids(
            args['date']), []

    @staticmethod
    def default_subscription_behaviour():
        return 'mandatory'


class PackageCoverage(model.CoopSQL):
    'Link Package Coverage'

    __name__ = 'ins_product.package-coverage'

    package = fields.Many2One('ins_product.coverage', 'Package')
    coverage = fields.Many2One('ins_product.coverage', 'Coverage')

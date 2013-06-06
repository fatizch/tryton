#-*- coding:utf-8 -*-
import copy

from trytond.pool import Pool
from trytond.pyson import Eval, Bool

from trytond.modules.coop_utils import model, business, utils, fields
from trytond.modules.insurance_product import Offered, product
from trytond.modules.insurance_product import PricingResultLine
from trytond.modules.insurance_product import EligibilityResultLine


__all__ = [
    'SimpleCoverage',
    'Coverage',
    'PackageCoverage',
    'CoverageComplementaryDataRelation',
]

SUBSCRIPTION_BEHAVIOUR = [
    ('mandatory', 'Mandatory'),
    ('proposed', 'Proposed'),
    ('optional', 'Optional'),
]

COULD_NOT_FIND_A_MATCHING_RULE = 'Could not find a matching rule'


class SimpleCoverage(Offered):
    'Simple Coverage'

    __name__ = 'ins_product.simple_coverage'

    products = fields.Many2Many(
        'ins_product.product-options-coverage',
        'coverage', 'product', 'Products',
        domain=[('currency', '=', Eval('currency'))],
        depends=['currency'])
    insurer = fields.Many2One('party.insurer', 'Insurer',
        states={'invisible': Bool(Eval('is_package'))},
        depends=['is_package'])
    family = fields.Selection([('default', 'default')], 'Family',
        states={
            'invisible': Bool(Eval('is_package')),
            'required': Bool(~Eval('is_package')),
        },
        depends=['is_package'])
    item_desc = fields.Many2One('ins_product.item_desc', 'Item Descriptor',
        required=True)
    currency = fields.Many2One('currency.currency', 'Currency', required=True)
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
    complementary_data_def = fields.Many2Many(
        'ins_product.coverage-complementary_data_def',
        'coverage', 'complementary_data_def', 'Complementary Data',
        domain=[('kind', 'in', ['contract', 'sub_elem'])])

    @classmethod
    def __setup__(cls):
        super(SimpleCoverage, cls).__setup__()
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

    @staticmethod
    def default_currency():
        return business.get_default_currency()

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

    def give_me_complementary_data_ids_aggregate(self, args):
        if not 'dd_args' in args:
            return [], []
        dd_args = args['dd_args']
        if not('options' in dd_args and dd_args['options'] != '' and
                self.code in dd_args['options'].split(';')):
            return [], []
        return self.get_complementary_data_def(
            [dd_args['kind']], args['date']), []

    @staticmethod
    def default_subscription_behaviour():
        return 'mandatory'

    def get_currency(self):
        return self.currency


class Coverage(model.CoopSQL, SimpleCoverage):
    'Coverage'

    __name__ = 'ins_product.coverage'

    benefits = fields.Many2Many('ins_product.coverage-benefit', 'coverage',
        'benefit', 'Benefits',
        context={
            'start_date': Eval('start_date'),
            'currency_digits': Eval('currency_digits'),
        },
        states={
            'readonly': ~Bool(Eval('start_date')),
            'invisible': Bool(Eval('is_package')),
        },
        depends=['currency_digits'])

    @classmethod
    def __setup__(cls):
        super(Coverage, cls).__setup__()
        cls._sql_constraints += [
            ('code_uniq', 'UNIQUE(code)', 'The code must be unique!'),
        ]

    @classmethod
    def delete(cls, entities):
        cls.delete_rules(entities)
        super(Coverage, cls).delete(entities)

    def get_currency(self):
        return self.currency

    @classmethod
    def _export_skips(cls):
        skips = super(Coverage, cls)._export_skips()
        skips.add('products')
        return skips


class PackageCoverage(model.CoopSQL):
    'Link Package Coverage'

    __name__ = 'ins_product.package-coverage'

    package = fields.Many2One('ins_product.coverage', 'Package')
    coverage = fields.Many2One('ins_product.coverage', 'Coverage')


class CoverageComplementaryDataRelation(model.CoopSQL):
    'Relation between Coverage and Complementary Data'

    __name__ = 'ins_product.coverage-complementary_data_def'

    coverage = fields.Many2One('ins_product.coverage', 'Coverage',
        ondelete='CASCADE')
    complementary_data_def = fields.Many2One(
        'ins_product.complementary_data_def',
        'Complementary Data', ondelete='RESTRICT')

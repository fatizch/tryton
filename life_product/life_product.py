#-*- coding:utf-8 -*-
import copy

from trytond.pool import PoolMeta
from trytond.model import fields
from trytond.pyson import Eval, Or, Bool

from trytond.modules.coop_utils import utils
from trytond.modules.coop_utils import date

from trytond.modules.insurance_product import ProductDefinition
from trytond.modules.insurance_product import EligibilityResultLine
from trytond.modules.insurance_product.business_rule.business_rule import \
    STATE_SIMPLE, STATE_SUB_SIMPLE

STATE_LIFE = (Eval('_parent_offered', {}).get('family') !=
    'life_product.definition')
FAMILY_LIFE = 'life_product.definition'

__all__ = [
    'LifeItemDescriptor',
    'LifeCoverage',
    'LifeProductDefinition',
    'LifeEligibilityRule',
    'LifeLossDesc',
    'LifeBenefitRule',
]


class LifeItemDescriptor():
    'Item Descriptor'

    __name__ = 'ins_product.item_desc'
    __metaclass__ = PoolMeta

    @classmethod
    def get_possible_item_kind(cls):
        res = super(LifeItemDescriptor, cls).get_possible_item_kind()
        res.append(('person', 'Person'))
        return res


class LifeCoverage():
    'Coverage'

    __name__ = 'ins_product.coverage'
    __metaclass__ = PoolMeta

    coverage_amount_rules = fields.One2Many('ins_product.coverage_amount_rule',
        'offered', 'Coverage Amount Rules',
        states={
            'invisible': Or(
                Bool(Eval('is_package')),
                Eval('family') != FAMILY_LIFE,
            )
        })
    is_coverage_amount_needed = fields.Function(
        fields.Boolean('Coverage Amount Needed', states={'invisible': True}),
        'get_is_coverage_amount_needed')

    @classmethod
    def __setup__(cls):
        super(LifeCoverage, cls).__setup__()
        cls.family = copy.copy(cls.family)
        if not cls.family.selection:
            cls.family.selection = []
        utils.append_inexisting(cls.family.selection,
            (FAMILY_LIFE, 'Life'))
        if ('default', 'default') in cls.family.selection:
            cls.family.selection.remove(('default', 'default'))

    def get_is_coverage_amount_needed(self, name=None):
        return not self.is_package and self.family == FAMILY_LIFE


class LifeProductDefinition(ProductDefinition):
    'Life Product Definition'

    __name__ = 'life_product.definition'

    @staticmethod
    def get_extension_model():
        return 'extension_life'

    @staticmethod
    def get_step_model(step_name):
        steps = {
            'extension': 'life_contract.extension_life_state',
        }
        return steps[step_name]


class LifeEligibilityRule():
    'Eligibility Rule'

    __metaclass__ = PoolMeta

    __name__ = 'ins_product.eligibility_rule'

    min_age = fields.Integer('Minimum Age',
        states={'invisible': Or(STATE_LIFE, STATE_SIMPLE)})
    max_age = fields.Integer('Maximum Age',
        states={'invisible': Or(STATE_LIFE, STATE_SIMPLE)})
    sub_min_age = fields.Integer('Minimum Age',
        states={'invisible': Or(STATE_LIFE, STATE_SUB_SIMPLE)})
    sub_max_age = fields.Integer('Maximum Age',
        states={'invisible': Or(STATE_LIFE, STATE_SUB_SIMPLE)})

    @classmethod
    def __setup__(cls):
        super(LifeEligibilityRule, cls).__setup__()
        cls.__doc__ = 'Eligibility Rule'

    def give_me_eligibility(self, args):
        res, errs = super(LifeEligibilityRule, self).give_me_eligibility(args)
        if not res.eligible:
            return res, errs
        if not self.config_kind == 'simple' or not(
                hasattr(self, 'min_age') or hasattr(self, 'max_age')):
            return res, errs
        subscriber = args['subscriber_person']
        age = date.number_of_years_between(
            subscriber.birth_date, args['date'])
        res = True
        details = []
        if hasattr(self, 'min_age') and self.min_age and age < self.min_age:
            res = False
            details.append(
                'Subscriber must be older than %s' % self.min_age)
        if hasattr(self, 'max_age') and self.max_age and age > self.max_age:
            res = False
            details.append(
                'Subscriber must be younger than %s' % self.max_age)
        return (EligibilityResultLine(eligible=res, details=details), errs)

    def give_me_sub_elem_eligibility(self, args):
        res, errs = super(
                LifeEligibilityRule, self).give_me_sub_elem_eligibility(args)
        if not res.eligible:
            return res, errs
        if not self.config_kind == 'simple' or not(
                hasattr(self, 'sub_min_age') or hasattr(self, 'sub_max_age')):
            return res, errs
        try:
            sub_elem = args['sub_elem']
        except KeyError:
            # If no Subscriber is found, automatic refusal
            return (EligibilityResultLine(
                False, ['Sub Element not defined in args']), [])
        person = args['person'] = sub_elem.person.get_person()
        age = date.number_of_years_between(
            person.birth_date, args['date'])
        res = True
        details = []
        if hasattr(self, 'sub_min_age') and self.sub_min_age and \
                age < self.sub_min_age:
            res = False
            details.append(
                '%s must be older than %s' % (
                    person.name, self.sub_min_age))
        if hasattr(self, 'sub_max_age') and self.sub_max_age and \
                age > self.sub_max_age:
            res = False
            details.append(
                '%s must be younger than %s' % (
                    person.name, self.sub_max_age))
        return (EligibilityResultLine(eligible=res, details=details), errs)


class LifeLossDesc():
    'Loss Desc'

    __name__ = 'ins_product.loss_desc'
    __metaclass__ = PoolMeta

    @classmethod
    def get_possible_item_kind(cls):
        res = super(LifeLossDesc, cls).get_possible_item_kind()
        res.append(('person', 'Person'))
        return res


class LifeBenefitRule():
    'Life Benefit Rule'

    __name__ = 'ins_product.benefit_rule'
    __metaclass__ = PoolMeta

    def get_coverage_amount(self, args):
        if 'option' in args and 'covered_person' in args:
            return args['option'].get_coverage_amount(args['covered_person'])

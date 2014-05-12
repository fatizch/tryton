#-*- coding:utf-8 -*-
from trytond.pool import PoolMeta
from trytond.pyson import Eval, Or, Bool

from trytond.modules.cog_utils import utils, fields
from trytond.modules.cog_utils import coop_date

from trytond.modules.offered import EligibilityResultLine
from trytond.modules.offered_insurance.business_rule.business_rule import \
    STATE_ADVANCED, STATE_SUB_SIMPLE

STATE_LIFE = (
    Eval('_parent_offered', {}).get('family') != 'life')

__metaclass__ = PoolMeta
__all__ = [
    'OptionDescription',
    'EligibilityRule',
    ]


class OptionDescription:
    __name__ = 'offered.option.description'

    coverage_amount_rules = fields.One2Many('offered.coverage_amount.rule',
        'offered', 'Coverage Amount Rules', states={
            'invisible': Or(
                Bool(Eval('is_package')),
                Eval('family') != 'life',
                )
            })
    is_coverage_amount_needed = fields.Function(
        fields.Boolean('Coverage Amount Needed', states={'invisible': True}),
        'get_is_coverage_amount_needed')

    @classmethod
    def __setup__(cls):
        super(OptionDescription, cls).__setup__()
        cls.family.selection.append(('life', 'Life'))

    def get_is_coverage_amount_needed(self, name=None):
        return not self.is_package and self.family == 'life'


class EligibilityRule:
    __name__ = 'offered.eligibility.rule'

    min_age = fields.Integer('Minimum Age',
        states={'invisible': Or(STATE_LIFE, STATE_ADVANCED)})
    max_age = fields.Integer('Maximum Age',
        states={'invisible': Or(STATE_LIFE, STATE_ADVANCED)})
    sub_min_age = fields.Integer('Minimum Age',
        states={'invisible': Or(STATE_LIFE, STATE_SUB_SIMPLE)})
    sub_max_age = fields.Integer('Maximum Age',
        states={'invisible': Or(STATE_LIFE, STATE_SUB_SIMPLE)})

    @classmethod
    def __setup__(cls):
        super(EligibilityRule, cls).__setup__()
        cls.__doc__ = 'Eligibility Rule'

    def give_me_eligibility(self, args):
        res, errs = super(EligibilityRule, self).give_me_eligibility(args)
        if not res.eligible:
            return res, errs
        if not self.config_kind == 'simple' or not(
                hasattr(self, 'min_age') or hasattr(self, 'max_age')):
            return res, errs
        details = []
        if 'subscriber_person' in args:
            subscriber = args['subscriber_person']
            age = coop_date.number_of_years_between(subscriber.birth_date,
                args['date'])
            res = True
            if getattr(self, 'min_age', None) and age < self.min_age:
                res = False
                details.append(
                    'Subscriber must be older than %s' % self.min_age)
            if getattr(self, 'max_age', None) and age > self.max_age:
                res = False
                details.append(
                    'Subscriber must be younger than %s' % self.max_age)
        return (EligibilityResultLine(eligible=res, details=details), errs)

    def give_me_sub_elem_eligibility(self, args):
        res, errs = super(
                EligibilityRule, self).give_me_sub_elem_eligibility(args)
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
        person = args['person'] = sub_elem.party.get_person()
        age = coop_date.number_of_years_between(
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

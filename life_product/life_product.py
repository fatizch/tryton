#-*- coding:utf-8 -*-
import copy

from trytond.pool import PoolMeta
from trytond.model import fields as fields

from trytond.modules.coop_utils import business as business
from trytond.modules.coop_utils import date as date

from trytond.modules.insurance_product import ProductDefinition
from trytond.modules.insurance_product import EligibilityResultLine

__all__ = ['LifeCoverage', 'LifeProductDefinition', 'LifeEligibilityRule']


class LifeCoverage():
    'Coverage'

    __metaclass__ = PoolMeta

    __name__ = 'ins_product.coverage'

    @classmethod
    def __setup__(cls):
        super(LifeCoverage, cls).__setup__()
        cls.family = copy.copy(cls.family)
        if not cls.family.selection:
            cls.family.selection = []
        if not ('life_product.definition', 'Life') in cls.family.selection:
            cls.family.selection.append(
                ('life_product.definition', 'Life'))
        if ('default', 'default') in cls.family.selection:
            cls.family.selection.append(
                ('default', 'default'))


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

    min_age = fields.Integer('Minimum Age')

    max_age = fields.Integer('Maximum Age')

    sub_min_age = fields.Integer('Minimum Age')

    sub_max_age = fields.Integer('Maximum Age')

    @classmethod
    def __setup__(cls):
        super(LifeEligibilityRule, cls).__setup__()
        cls.__doc__ = 'Eligibility Rule'

    def give_me_eligibility(self, args):
        if not self.config_kind == 'simple' or not(
                hasattr(self, 'min_age') or hasattr(self, 'max_age')):
            return super(LifeEligibilityRule, self).give_me_eligibility(args)
        try:
            business.update_args_with_subscriber(args)
        except business.ArgsDoNotMatchException:
            # If no Subscriber is found, automatic refusal
            return (EligibilityResultLine(
                False, ['Subscriber not defined in args']), [])
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
        return (EligibilityResultLine(eligible=res, details=details), [])

    def give_me_sub_elem_eligibility(self, args):
        if not self.sub_elem_config_kind == 'simple' or not (
                hasattr(self, 'sub_min_age') or hasattr(self, 'sub_max_age')):
            return super(
                LifeEligibilityRule, self).give_me_sub_elem_eligibility(args)
        try:
            sub_elem = args['sub_elem']
        except KeyError:
            # If no Subscriber is found, automatic refusal
            return (EligibilityResultLine(
                False, ['Sub Element not defined in args']), [])
        person = args['person'] = sub_elem.person
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
        return (EligibilityResultLine(eligible=res, details=details), [])

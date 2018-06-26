# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

from trytond.modules.coog_core import fields
from trytond.pyson import Eval, And, Bool

__all__ = [
    'BenefitRule',
    'ManageOptionBenefitsDisplayer',
    ]


class BenefitRule:
    __metaclass__ = PoolMeta
    __name__ = 'benefit.rule'

    revaluation_on_basic_salary = fields.Boolean('Revaluation on basic salary',
        help='If set revaluation will be calculated on basic salary instead '
        'of indemnification amount',
        states={'invisible': And(Bool(Eval('is_group')),
                ~Eval('force_revaluation_on_basic_salary'))},
        depends=['force_revaluation_on_basic_salary', 'is_group'])
    force_revaluation_on_basic_salary = fields.Boolean(
        'Force revaluation on basic salary',
        help='Get revaluation on basic salary from product if True',
        states={'invisible': ~Eval('is_group')},
        depends=['is_group'])

    @staticmethod
    def default_revaluation_on_basic_salary():
        return False

    @staticmethod
    def default_force_revaluation_on_basic_salary():
        return False

    def option_benefit_at_date(self, option, date):
        if not option:
            return ''
        version = option.get_version_at_date(date)
        option_benefit = version.get_benefit(self.benefit)
        return option_benefit

    def process_revaluation_on_basic_salary(self, service):
        if self.force_revaluation_on_basic_salary:
            return self.revaluation_on_basic_salary
        else:
            option = self.option_benefit_at_date(service.option,
                service.loss.start_date)
            return option.revaluation_on_basic_salary

    def do_calculate_revaluation_rule(self, args):
        if ('indemnification' in args and
                self.process_revaluation_on_basic_salary(
                    args['indemnification'].service)):
            # do not calculate revaluation after indemnification calculation
            # if revaluation on basic salary
            return [args]
        return super(BenefitRule, self).do_calculate_revaluation_rule(args)

    @classmethod
    def calculation_dates(cls, indemnification, start_date, end_date):
        # Call revaluation rule to know revaluation date change in order to
        # force recalculation of basic salary
        dates = super(BenefitRule, cls).calculation_dates(indemnification,
            start_date, end_date)
        benefit_rule = indemnification.service.benefit.benefit_rules[0]
        if not benefit_rule.process_revaluation_on_basic_salary:
            return dates
        args = {
            'indemnification_detail_start_date': start_date,
            'indemnification_detail_end_date': end_date,
            'base_amount': 1,
            'date': indemnification.start_date,
            'description': '',
            }
        indemnification.init_dict_for_rule_engine(args)
        res = indemnification.service.benefit.benefit_rules[
            0].calculate_revaluation_rule(args)
        for period in res:
            dates.add(period['start_date'])
        return dates


class ManageOptionBenefitsDisplayer:
    __metaclass__ = PoolMeta
    __name__ = 'contract.manage_option_benefits.option'

    @classmethod
    def get_option_benefit_fields(cls):
        return super(
            ManageOptionBenefitsDisplayer, cls).get_option_benefit_fields() + (
                'salary_mode', 'net_salary_mode', 'net_calculation_rule')

# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.modules.rule_engine import check_args

__metaclass__ = PoolMeta
__all__ = [
    'RuleEngineRuntime',
    'RuleEngine',
    ]


class RuleEngine:
    __name__ = 'rule_engine'

    @classmethod
    def __setup__(cls):
        super(RuleEngine, cls).__setup__()
        cls.type_.selection.append(('benefit_net_salary_calculation',
                'Benefit: Net Salary Calculation'))


class RuleEngineRuntime:
    __name__ = 'rule_engine.runtime'

    @classmethod
    @check_args('curr_salary')
    def _re_get_range_by_name(cls, args, range_name=None, fixed=False,
            codes_list=None):
        return args['curr_salary'].get_range(range_name, fixed, codes_list)

    @classmethod
    @check_args('service')
    def _re_get_gross_salary(cls, args):
        if 'curr_salary' in args:
            return args['curr_salary'].gross_salary
        else:
            return args['service'].gross_salary

    @classmethod
    @check_args('service')
    def _re_get_net_salary(cls, args):
        if 'curr_salary' in args:
            return args['curr_salary'].net_salary
        else:
            return args['service'].net_salary

    @classmethod
    @check_args('service')
    def _re_basic_salary(cls, args, salaries_def):
        current_salary = args.get('curr_salary', None)
        return args['service'].calculate_basic_salary(salaries_def,
            current_salary=current_salary)

    @classmethod
    @check_args('service')
    def _re_is_net_limite(cls, args):
        return args['service'].benefit.benefit_rules[0]. \
            option_benefit_at_date(args['service'].option,
                args['service'].loss.start_date).net_salary_mode

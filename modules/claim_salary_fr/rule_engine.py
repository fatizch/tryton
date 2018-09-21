# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal

from trytond.pool import PoolMeta
from trytond.modules.rule_engine import check_args

__all__ = [
    'RuleEngineRuntime',
    'RuleEngine',
    ]


class RuleEngine:
    __metaclass__ = PoolMeta
    __name__ = 'rule_engine'

    @classmethod
    def __setup__(cls):
        super(RuleEngine, cls).__setup__()
        cls.type_.selection.append(('benefit_net_salary_calculation',
                'Benefit: Net Salary Calculation'))


class RuleEngineRuntime:
    __metaclass__ = PoolMeta
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
        service = args['service']
        if 'curr_salary' in args:
            return args['curr_salary'].net_salary
        else:
            if service.net_salary:
                return service.net_salary
            else:
                for s in reversed([x for x in service.claim.delivered_services
                            if x != service]):
                    if s.net_salary:
                        return s.net_salary
        return Decimal(0)

    @classmethod
    @check_args('service')
    def _re_basic_salary(cls, args, salaries_def, with_revaluation=True):
        current_salary = args.get('curr_salary', None)
        return args['service'].calculate_basic_salary(salaries_def,
            current_salary=current_salary,
            args=args if with_revaluation else None)

    @classmethod
    @check_args('service')
    def _re_is_net_limite(cls, args):
        return args['service'].benefit.benefit_rules[0]. \
            option_benefit_at_date(args['service'].option,
                args['service'].loss.start_date).net_salary_mode

    @classmethod
    @check_args('service')
    def _re_revaluation_on_basic_salary(cls, args):
        return args['service'].benefit.benefit_rules[
            0].process_revaluation_on_basic_salary(args['service'])

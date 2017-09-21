# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

from trytond.modules.rule_engine import check_args

__metaclass__ = PoolMeta

__all__ = [
    'RuleEngineRuntime',
    ]


class RuleEngineRuntime:
    __name__ = 'rule_engine.runtime'

    @classmethod
    def get_other_option_data(cls, coverage_code, meth_name, base_args, *args,
            **kwargs):
        '''
            This method calls the rule function "meth_name" for the closest
            option with a coverage matching "coverage_code" relatively to the
            current "base_args" option
        '''
        cur_option = base_args['option']
        new_option = cur_option.get_sister_option(coverage_code)
        base_args['option'] = new_option
        res = getattr(cls, meth_name)(base_args, *args, **kwargs)
        base_args['option'] = cur_option
        return res

    @classmethod
    @check_args('contract', 'date')
    def _re_number_of_covered_elements(cls, args):
        contract = args['contract']
        return len(contract.get_covered_elements_at_date(args['date']))

    @classmethod
    @check_args('contract')
    def _re_initial_number_of_sub_covered_elements(cls, args):
        return args['contract'].initial_number_of_sub_covered_elements or 0

    @classmethod
    @check_args('elem', 'contract', 'coverage')
    def _re_covered_element_rank(cls, args):
        elem = args['elem']
        contract = args['contract']
        i = 0
        for cov_elem in getattr(contract, 'covered_elements', []):
            for option in cov_elem.options:
                if option.coverage == args['coverage']:
                    i += 1
            if cov_elem == elem:
                return i

    @classmethod
    @check_args('contract', 'coverage')
    def _re_number_of_covered_elements_for_coverage(cls, args):
        contract = args['contract']
        i = 0
        for cov_elem in getattr(contract, 'covered_elements', []):
            for option in cov_elem.options:
                if option.coverage == args['coverage']:
                    i += 1
        return i

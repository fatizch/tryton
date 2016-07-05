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
    @check_args('contract', 'date')
    def _re_number_of_covered_elements(cls, args):
        contract = args['contract']
        return len(contract.get_covered_elements_at_date(args['date']))

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

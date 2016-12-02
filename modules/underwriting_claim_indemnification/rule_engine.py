# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

from trytond.modules.rule_engine import check_args

__all__ = [
    'RuleEngineRuntime',
    ]


class RuleEngineRuntime:
    __metaclass__ = PoolMeta
    __name__ = 'rule_engine.runtime'

    @classmethod
    @check_args('service')
    def _re_underwriting_decisions(cls, args):
        start = cls._re_indemnification_period_start_date(args)
        end = cls._re_indemnification_period_end_date(args)
        service = args['service']
        decisions = []
        for elem in service.underwritings_at_date(start, end):
            decisions.append(elem.get_decision().code)
        return decisions

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
    def _re_get_service_eligibility_status(cls, args):
        service = args['service']
        return service.eligibility_status

    @classmethod
    @check_args('service')
    def _re_get_service_eligibility_decision_code(cls, args):
        service = args['service']
        if service.eligibility_decision:
            return service.eligibility_decision.code

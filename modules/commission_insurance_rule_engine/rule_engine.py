from trytond.pool import PoolMeta

from trytond.modules.rule_engine import check_args

__metaclass__ = PoolMeta
__all__ = [
    'RuleEngineRuntime',
    ]


class RuleEngineRuntime:
    __name__ = 'rule_engine.runtime'

    @classmethod
    @check_args('contract')
    def _re_commission_plan(cls, args):
        contract = args['contract']
        if contract.agent:
            return contract.agent.plan.rule_engine_key

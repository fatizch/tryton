
from trytond.pool import PoolMeta
from trytond.modules.rule_engine import check_args

__metaclass__ = PoolMeta
__all__ = [
    'RuleEngineRuntime',
    ]


class RuleEngineRuntime:
    __name__ = 'rule_engine.runtime'

    @classmethod
    @check_args('indemnification')
    def _re_is_employee_beneficiary(cls, args):
        return (args['indemnification'].service.claim.claimant
                == args['indemnification'].beneficiary)

# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from trytond.pool import PoolMeta

from trytond.modules.rule_engine import check_args


__all__ = [
    'RuleEngineRuntime',
    ]


class RuleEngineRuntime:
    __metaclass__ = PoolMeta
    __name__ = 'rule_engine.runtime'

    @classmethod
    @check_args('contract')
    def _re_revaluation_max_revaluation_date(cls, args):
        contract = args['contract']
        if (contract and
                contract.post_termination_claim_behaviour ==
                'lock_indemnifications'):
            return contract.end_date
        return datetime.date.max

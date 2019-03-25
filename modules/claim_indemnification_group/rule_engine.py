# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from trytond.pool import PoolMeta

from trytond.modules.rule_engine import check_args
from trytond.modules.coog_core import utils


__all__ = [
    'RuleEngineRuntime',
    ]


class RuleEngineRuntime(metaclass=PoolMeta):
    __name__ = 'rule_engine.runtime'

    @classmethod
    @check_args('contract')
    def _re_revaluation_max_revaluation_date(cls, args):
        contract = args['contract']
        if (contract and
                contract.post_termination_claim_behaviour ==
                'lock_indemnifications'):
            return contract.final_end_date
        return datetime.date.max

    @classmethod
    @check_args('contract', 'option')
    def _re_revaluation_min_revaluation_date(cls, args):
        contract = args['contract']
        option = args['option']
        if (contract and option and
                option.previous_claims_management_rule in (
                    'in_complement', 'in_complement_previous_rule')):
            return contract.initial_start_date
        return datetime.date.min

    @classmethod
    @check_args('service')
    def _re_get_previous_insurer_base_amount(cls, args):
        service = args['service']
        return utils.get_value_at_date(service.extra_datas,
            service.loss.start_date).previous_insurer_base_amount

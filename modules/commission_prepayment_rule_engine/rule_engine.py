# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool

from trytond.modules.rule_engine import check_args

__all__ = [
    'RuleEngineRuntime',
    ]


class RuleEngineRuntime:
    __metaclass__ = PoolMeta
    __name__ = 'rule_engine.runtime'

    @classmethod
    @check_args('option')
    def _re_option_first_year_premium(cls, args):
        option = args['option']
        if option:
            return option.first_year_premium

    @classmethod
    @check_args('contract')
    def re_will_delete_unredeemed_prepayment(cls, args):
        configuration = Pool().get('offered.configuration').get_singleton()
        return args['contract'].termination_reason in \
            configuration.remove_commission_for_sub_status

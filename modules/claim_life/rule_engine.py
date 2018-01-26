# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

from trytond.modules.rule_engine import check_args

__metaclass__ = PoolMeta
__all__ = [
    'RuleEngineRuntime',
    ]


class RuleEngineRuntime:
    __metaclass__ = PoolMeta
    __name__ = 'rule_engine.runtime'

    @classmethod
    @check_args('loss')
    def _re_is_a_relapse(cls, args):
        return args['loss'].is_a_relapse

    @classmethod
    @check_args('indemnification')
    def _re_is_covered_element_beneficiary(cls, args):
        return (args['indemnification'].service.loss.covered_person
                == args['indemnification'].beneficiary)

    @classmethod
    @check_args('beneficiary_definition')
    def _re_beneficiary_share(cls, args):
        return args['beneficiary_definition'].share

    @classmethod
    def _re_initial_std_start_date(cls, args):
        if 'loss' in args and args['loss'].initial_std_start_date:
            return args['loss'].initial_std_start_date
        if 'claim' in args:
            for loss in args['claim'].losses:
                if loss.loss_desc_kind == 'std':
                    return loss.start_date

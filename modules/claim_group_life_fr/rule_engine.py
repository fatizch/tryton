# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import PoolMeta

from trytond.modules.rule_engine import check_args
from trytond.modules.coog_core import coog_date


__metaclass__ = PoolMeta
__all__ = [
    'RuleEngineRuntime',
    ]


class RuleEngineRuntime:
    __name__ = 'rule_engine.runtime'

    @classmethod
    @check_args('loss')
    def _re_total_hospitalisation_period(cls, args):
        return sum([coog_date.number_of_days_between(
                    x.start_date, x.end_date)
                for x in args['loss'].hospitalisation_periods])

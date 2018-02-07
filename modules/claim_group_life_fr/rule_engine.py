# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

from trytond.modules.rule_engine import check_args
from trytond.modules.coog_core import coog_date


__all__ = [
    'RuleEngineRuntime',
    ]


class RuleEngineRuntime:
    __metaclass__ = PoolMeta
    __name__ = 'rule_engine.runtime'

    @classmethod
    @check_args('loss')
    def _re_total_hospitalisation_period(cls, args):
        return sum([coog_date.number_of_days_between(
                    x.start_date, x.end_date)
                for x in args['loss'].hospitalisation_periods])

    @classmethod
    @check_args('indemnification', 'indemnification_detail_start_date')
    def _re_ijss_before_part_time(cls, args):
        delivered = args['indemnification'].service
        at_date = args['indemnification_detail_start_date']
        ijss = {e.date or delivered.loss.start_date:
            e.extra_data_values['ijss']
            if 'ijss' in e.extra_data_values else 0
            for e in delivered.extra_datas
            if (e.date or delivered.loss.start_date) < at_date}
        dates = sorted(ijss.keys(), reverse=True)
        part_times = [x for x in delivered.loss.deduction_periods
            if x.deduction_kind.code == 'part_time' and x.start_date
            and x.start_date < at_date]

        def part_time_period_at_date(date):
            for part_time in part_times:
                if part_time.start_date <= date and part_time.end_date >= date:
                    return part_time

        for date in dates:
            if not part_time_period_at_date(date):
                return ijss[date]

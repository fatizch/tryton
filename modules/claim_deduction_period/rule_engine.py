# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
from decimal import Decimal

from trytond.pool import PoolMeta

from trytond.modules.rule_engine.rule_engine import check_args


__all__ = [
    'RuleEngineRuntime',
    ]


class RuleEngineRuntime(metaclass=PoolMeta):
    __name__ = 'rule_engine.runtime'

    @classmethod
    def _period_is_valid(cls, loss, period, start_date, end_date,
            allowed):
        if period.deduction_kind not in allowed:
            return False
        if period.start_date > (end_date or datetime.date.min):
            return False
        latest_start = max(start_date, period.start_date)
        if not period.end_date:
            cls.append_error((loss, period, start_date, end_date),
                'the end date must be defined for '
                'the deduction %s from %s' % (period.deduction_kind.name,
                    period.start_date))
        earliest_end = min(end_date, period.end_date)
        days = (earliest_end - latest_start).days + 1
        if days <= 0:
            return False
        return True

    @classmethod
    @check_args('loss')
    def _re_get_deduction_periods(cls, args, code, start_date,
            end_date):
        loss = args['loss']
        allowed = {x for x in loss.loss_desc.deduction_period_kinds
            if not code or x.code == code}
        periods = []
        if code and code not in (x.code
                for x in loss.loss_desc.deduction_period_kinds):
            return periods
        for period in loss.deduction_periods:
            if not cls._period_is_valid(loss, period, start_date, end_date,
                    allowed):
                continue
            periods.append((period.start_date, period.end_date))
        return periods

    @classmethod
    @check_args('loss')
    def _re_get_deduction_period_amount(cls, args, code, start_date,
            end_date, daily=True, round=False):
        loss = args['loss']
        amount = Decimal(0)
        allowed = {x for x in loss.loss_desc.deduction_period_kinds
            if not code or x.code == code}

        if code and code not in (x.code
                for x in loss.loss_desc.deduction_period_kinds):
            return amount
        for period in loss.deduction_periods:
            if not cls._period_is_valid(loss, period, start_date, end_date,
                    allowed):
                continue
            latest_start = max(start_date, period.start_date)
            earliest_end = min(end_date, period.end_date)
            days = (earliest_end - latest_start).days + 1
            if daily:
                amount += period.on_change_with_daily_amount(round=round)
            else:
                amount += days * period.on_change_with_daily_amount(
                    round=round)
        return amount

# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal

from trytond.pool import PoolMeta

from trytond.modules.rule_engine.rule_engine import check_args


__all__ = [
    'RuleRuntime',
    ]


class RuleRuntime:
    __metaclass__ = PoolMeta
    __name__ = 'rule_engine.runtime'

    @classmethod
    @check_args('loss')
    def _re_get_deduction_period_amount(self, args, code, start_date,
            end_date, round=False):
        loss = args['loss']
        amount = Decimal(0)
        allowed = {x for x in loss.loss_desc.deduction_period_kinds
            if not code or x.code == code}

        if code and code not in (x.code
                for x in loss.loss_desc.deduction_period_kinds):
            return amount
        for period in loss.deduction_periods:
            if period.deduction_kind not in allowed:
                continue
            latest_start = max(start_date, period.start_date)
            earliest_end = min(end_date, period.end_date)
            days = (earliest_end - latest_start).days + 1
            if days <= 0:
                continue
            amount += days * period.on_change_with_daily_amount(round=round)
        return amount

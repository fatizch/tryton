# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from trytond.pool import PoolMeta

from trytond.modules.rule_engine import check_args
from trytond.modules.cog_utils import coop_date


__metaclass__ = PoolMeta
__all__ = [
    'RuleEngineRuntime',
    ]


class RuleEngineRuntime:
    __name__ = 'rule_engine.runtime'

    @classmethod
    def get_lowest_level_object(cls, args):
        if 'service' in args:
            return args['service']
        return super(RuleEngineRuntime, cls).get_lowest_level_object(args)

    @classmethod
    @check_args('service')
    def _re_service_expense(cls, args, expense_code):
        del_service = args['service']
        return del_service.get_expense(expense_code, args['currency'])

    @classmethod
    @check_args('service')
    def _re_service_total_expenses(cls, args):
        del_service = args['service']
        return del_service.get_total_expense(args['currency'])

    @classmethod
    @check_args('claim')
    def _re_claim_declaration_date(cls, args):
        return args['claim'].declaration_date

    @classmethod
    @check_args('loss')
    def _re_loss_start_date(cls, args):
        return args['loss'].start_date

    @classmethod
    @check_args('claim')
    def _re_last_loss_end_date(cls, args):
        res = datetime.date.min
        for loss in args['claim'].losses:
            res = max(loss.end_date or datetime.date.min, res)
        return res if res != datetime.date.min else None

    @classmethod
    @check_args('loss')
    def _re_total_hospitalisation_period(cls, args):
        return sum([coop_date.number_of_days_between(
                    x.start_date, x.end_date)
                for x in args['loss'].hospitalisation_periods])

    @classmethod
    @check_args('loss')
    def _re_loss_desc_code(cls, args):
        return args['loss'].loss_desc.code

    @classmethod
    @check_args('loss')
    def _re_event_desc_code(cls, args):
        return args['loss'].event_desc.code

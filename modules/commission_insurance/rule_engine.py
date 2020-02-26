# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal

from trytond.pool import PoolMeta

from trytond.modules.rule_engine import check_args

__all__ = [
    'RuleEngineRuntime',
    ]


class RuleEngineRuntime(metaclass=PoolMeta):
    __name__ = 'rule_engine.runtime'

    @classmethod
    @check_args('contract')
    def _re_commission_plan(cls, args):
        contract = args['contract']
        if contract.agent:
            return contract.agent.plan.rule_engine_key

    @classmethod
    @check_args('amount')
    def _re_invoice_line_amount(cls, args):
        return args['amount']

    @classmethod
    @check_args('invoice_line')
    def _re_invoice_line_start_date(cls, args):
        if args['invoice_line']:
            return args['invoice_line'].coverage_start

    @classmethod
    @check_args('invoice_line')
    def _re_invoice_line_end_date(cls, args):
        if args['invoice_line']:
            return args['invoice_line'].coverage_end

    @classmethod
    @check_args('commission_start_date')
    def _re_commission_start_date(cls, args):
        return args['commission_start_date']

    @classmethod
    @check_args('commission_end_date')
    def _re_commission_end_date(cls, args):
        return args['commission_end_date']

    @classmethod
    @check_args('commission_data')
    def _re_agent_custom_commission_rate(cls, args):
        return args['commission_data'].rate

    @classmethod
    @check_args('contract')
    def _re_contract_premium_commission_rate(cls, args):
        return sum([
                x.premium_rate or 0
                for x in args['contract']._calculated_commission_data],
            Decimal(0))

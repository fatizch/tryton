# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal
from dateutil.relativedelta import relativedelta

from sql import Literal
from sql.aggregate import Sum, Max

from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.modules.rule_engine import check_args

__metaclass__ = PoolMeta
__all__ = [
    'RuleEngineRuntime',
    ]


class RuleEngineRuntime:
    __name__ = 'rule_engine.runtime'

    @classmethod
    @check_args('option', 'agent')
    def re_commission_sum_for_option(cls, args):
        pool = Pool()
        cursor = Transaction().connection.cursor()
        commission = pool.get('commission').__table__()

        cursor.execute(*commission.select(Sum(commission.amount),
            where=((commission.commissioned_option == args['option'].id) &
                (commission.agent == args['agent'].id) &
                (commission.is_recovery == Literal(False)))))
        res = cursor.fetchall()
        return res[0][0] or Decimal(0)

    @classmethod
    @check_args('option')
    def re_last_paid_invoice_end_date(cls, args):
        pool = Pool()
        cursor = Transaction().connection.cursor()
        contract_invoice = pool.get('contract.invoice').__table__()
        invoice_line = pool.get('account.invoice.line').__table__()
        details = pool.get('account.invoice.line.detail').__table__()

        query_table = contract_invoice.join(invoice_line, condition=(
                contract_invoice.invoice == invoice_line.invoice)
            ).join(details, condition=(
                invoice_line.id == details.invoice_line))
        cursor.execute(*query_table.select(Max(contract_invoice.end),
            where=((details.option == args['option'].id))))
        res = cursor.fetchall()
        return res[0][0]

    @classmethod
    @check_args('option', 'agent', 'contract')
    def re_prorated_recovery_for_yearly_prepayments(cls, args, at_date,
            nb_month):
        Agent = Pool().get('commission.agent')
        agent = args['agent']
        option = args['option']
        contract = args['contract']
        key = (agent.id, option.id)

        one_year = contract.initial_start_date + relativedelta(
            years=1, days=-1)

        if at_date <= one_year:
            # First Year: it's all prepayment
            prepayment_amount = Agent.sum_of_commissions([key])
            return prepayment_amount[key] * 12 / nb_month
        else:
            # Only use first year prepayment
            com = Agent.commissions_until_date([key], one_year)
            if key not in com:
                return Decimal(0)
            redeemed_com = com[key]['redeemed_commission']
            commission = com[key]['commission']
            redeemend_end_date = contract.initial_start_date + \
                relativedelta(months=nb_month, days=-1)
            redeemed_duration = (redeemend_end_date -
                contract.initial_start_date).days + 1
            option_duration = (at_date - contract.initial_start_date).days + 1
            return (redeemed_com + commission) * (1 - option_duration /
                Decimal(redeemed_duration))

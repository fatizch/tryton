from decimal import Decimal
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
        cursor = Transaction().cursor
        commission = pool.get('commission').__table__()

        cursor.execute(*commission.select(Sum(commission.amount),
            where=((commission.commissioned_option == args['option'].id) &
                commission.agent == args['agent'].id) &
                commission.invoice_line != None))
        res = cursor.fetchall()
        return res[0][0] or Decimal(0)

    @classmethod
    @check_args('option')
    def re_last_paid_invoice_end_date(cls, args):
        pool = Pool()
        cursor = Transaction().cursor
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

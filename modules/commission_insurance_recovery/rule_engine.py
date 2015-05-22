from decimal import Decimal
from sql.aggregate import Sum
from sql.operators import Concat

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
        invoice_line = pool.get('account.invoice.line').__table__()
        details = pool.get('account.invoice.line.detail').__table__()

        query_table = commission.join(invoice_line, condition=(
                commission.origin == (Concat('account.invoice.line,',
                        invoice_line.id)))
            ).join(details, condition=(
                invoice_line.id == details.invoice_line))
        cursor.execute(*query_table.select(Sum(commission.amount),
            where=((details.option == args['option'].id) and
                commission.agent == args['agent'].id)))
        res = cursor.fetchall()
        return res[0][0] or Decimal(0)

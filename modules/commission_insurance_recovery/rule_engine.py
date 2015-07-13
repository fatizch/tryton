from decimal import Decimal
from sql.aggregate import Sum

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
            where=((commission.commissioned_option == args['option'].id) and
                commission.agent == args['agent'].id)))
        res = cursor.fetchall()
        return res[0][0] or Decimal(0)

from decimal import Decimal
from sql import Cast
from sql.aggregate import Sum
from sql.conditionals import Coalesce
from sql.operators import Concat

from trytond.transaction import Transaction
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval

from trytond.modules.cog_utils import fields


__metaclass__ = PoolMeta
__all__ = [
    'MoveBreakdown',
    'Move',
    ]


class MoveBreakdown:
    __name__ = 'account.move.breakdown'

    commissions = fields.Numeric('Commissions')
    total_base_com = fields.Numeric('Total with coms')

    def ventilate_amounts(self, work_set):
        ratio = super(MoveBreakdown, self).ventilate_amounts(work_set)
        self.commissions = work_set.move.com_amount * ratio
        self.total_base_com = self.base_total
        self.base_total = self.base_total - self.commissions
        return ratio


class Move:
    __name__ = 'account.move'

    com_details = fields.One2ManyDomain('account.move.line', 'move',
        'Commissions', domain=[
            ('account.kind', '!=', 'receivable'),
            ('second_origin.kind', '=', 'commission',
                'offered.option.description'),
            ])
    com_amount = fields.Function(
        fields.Numeric('Com amount'),
        'get_com_amount')
    wo_com_amount = fields.Function(
        fields.Numeric('Amount w/o com'),
        'get_wo_com_amount')

    @classmethod
    def get_com_amount(cls, moves, name):
        res = dict((m.id, Decimal('0.0')) for m in moves)
        pool = Pool()
        cursor = Transaction().cursor

        move_line = pool.get('account.move.line').__table__()
        account = pool.get('account.account').__table__()
        move = pool.get('account.move').__table__()
        coverage = pool.get('offered.option.description').__table__()

        query_table = move_line.join(move,
            condition=(move.id == move_line.move)
            ).join(account, condition=(account.id == move_line.account))
        cursor.execute(*query_table.select(move.id, Sum(
                    Coalesce(move_line.credit, 0)
                    - Coalesce(move_line.debit, 0)),
                where=(account.kind != 'receivable')
                & (move_line.second_origin.in_(coverage.select(
                            Concat('offered.option.description,',
                                Cast(coverage.id, 'VARCHAR')),
                            where=(coverage.kind == 'commission'))))
                & (account.active)
                & (move.id.in_([m.id for m in moves])),
                group_by=move.id))
        for move_id, sum in cursor.fetchall():
            # SQLite uses float for SUM
            if not isinstance(sum, Decimal):
                sum = Decimal(str(sum))
            res[move_id] = sum
        return res

    def get_wo_com_amount(self, name):
        return self.wo_tax_amount - self.com_amount - self.fee_amount

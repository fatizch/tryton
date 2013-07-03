from decimal import Decimal

from trytond.transaction import Transaction
from trytond.pool import PoolMeta

from trytond.modules.coop_utils import fields


__all__ = [
    'Move',
    ]


class Move():
    'Move'

    __metaclass__ = PoolMeta
    __name__ = 'account.move'

    com_details = fields.One2ManyDomain('account.move.line', 'move',
        'Commissions', domain=[('account.kind', '!=', 'receivable'),
            ('second_origin.kind', '=', 'commission', 'offered.coverage')])
    com_amount = fields.Function(
        fields.Numeric('Com amount'),
        'get_com_amount')
    wo_com_amount = fields.Function(
        fields.Numeric('Amount w/o com'),
        'get_wo_com_amount')

    @classmethod
    def get_com_amount(cls, moves, name):
        res = dict((m.id, Decimal('0.0')) for m in moves)
        cursor = Transaction().cursor

        cursor.execute('SELECT m.id, '
                'SUM((COALESCE(l.credit, 0) - COALESCE(l.debit, 0))) '
            'FROM account_move_line AS l, account_account AS a '
            ', account_move as m '
            'WHERE a.id = l.account '
                'AND a.kind != \'receivable\' '
                'AND m.id IN (SELECT id FROM "account_move" '
                    'WHERE CAST(SUBSTR(second_origin, '
                            'POSITION(\',\' IN second_origin) + 1) '
                        'AS INT4) '
                        'IN (SELECT id FROM "offered_coverage" '
                            'WHERE kind = \'commission\')) '
                'AND a.active '
                'AND l.move = m.id '
                'AND m.id IN (' + ','.join(('%s',) * len(moves)) + ') '
            'GROUP BY m.id', [m.id for m in moves])
        for move_id, sum in cursor.fetchall():
            # SQLite uses float for SUM
            if not isinstance(sum, Decimal):
                sum = Decimal(str(sum))
            res[move_id] = sum
        return res

    def get_wo_com_amount(self, name):
        return self.wo_tax_amount - self.com_amount - self.fee_amount

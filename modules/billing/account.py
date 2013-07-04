from decimal import Decimal

from trytond.transaction import Transaction
from trytond.pool import PoolMeta, Pool
from trytond.modules.coop_utils import fields

__all__ = ['Move', 'MoveLine', 'Account']
__metaclass__ = PoolMeta


class Move:
    __name__ = 'account.move'

    billing_period = fields.Many2One('billing.period', 'Billing Period',
        ondelete='RESTRICT')
    total_amount = fields.Function(
        fields.Numeric('Total due amount'),
        'get_basic_amount', searcher='search_basic_amount')
    wo_tax_amount = fields.Function(
        fields.Numeric('Total Amount w/o taxes'),
        'get_wo_tax_amount')
    tax_amount = fields.Function(
        fields.Numeric('Tax amount'),
        'get_basic_amount', searcher='search_basic_amount')
    wo_fee_amount = fields.Function(
        fields.Numeric('Amount w/o fees'),
        'get_wo_fee_amount')
    fee_amount = fields.Function(
        fields.Numeric('Fee amount'),
        'get_basic_amount', searcher='search_basic_amount')
    contract = fields.Function(
        fields.Many2One('contract.contract', 'Contract'),
        'get_contract')
    schedule = fields.One2ManyDomain('account.move.line', 'move', 'Schedule',
        domain=[('account.kind', '=', 'receivable')])
    coverage_details = fields.One2ManyDomain('account.move.line', 'move',
        'Details', domain=[('account.kind', '!=', 'receivable'), ['OR',
                ['AND',
                    ('second_origin', 'like', 'offered.coverage,%'),
                    ('second_origin.kind', '=', 'insurance',
                        'offered.coverage')
                ],
                ('second_origin', 'like', 'offered.product,%')]])
    tax_details = fields.One2ManyDomain('account.move.line', 'move', 'Taxes',
        domain=[('account.kind', '!=', 'receivable'),
                ('second_origin', 'like', 'coop_account.tax_desc,%')])
    fee_details = fields.One2ManyDomain('account.move.line', 'move', 'Fees',
        domain=[('account.kind', '!=', 'receivable'),
            ('second_origin', 'like', 'coop_account.fee_desc,%')])

    @classmethod
    def _get_origin(cls):
        return super(Move, cls)._get_origin() + ['contract.contract']

    @classmethod
    def get_basic_amount(cls, moves, name):
        res = dict((m.id, Decimal('0.0')) for m in moves)
        cursor = Transaction().cursor

        extra_clause = ''
        account_clause = 'AND a.kind = \'receivable\' '
        sign = 1
        if name in ('tax_amount', 'fee_amount'):
            extra_clause = 'AND '
            extra_clause += 'l.second_origin LIKE '
            extra_clause += '\'coop_account.%s_desc' % name[0:3]
            extra_clause += ',%%\' '
            account_clause = 'AND a.kind != \'receivable\' '
            sign = -1

        cursor.execute('SELECT m.id, '
                'SUM((COALESCE(l.debit, 0) - COALESCE(l.credit, 0))) '
            'FROM account_move_line AS l, account_account AS a '
            ', account_move as m '
            'WHERE a.id = l.account '
                '' + account_clause + 'AND a.active '
                '' + extra_clause + 'AND l.move = m.id '
                'AND m.id IN (' + ','.join(('%s',) * len(moves)) + ') '
            'GROUP BY m.id', [m.id for m in moves])
        for move_id, sum in cursor.fetchall():
            # SQLite uses float for SUM
            if not isinstance(sum, Decimal):
                sum = Decimal(str(sum))
            res[move_id] = sum * sign
        return res

    @classmethod
    def search_basic_amount(cls, name, clause):
        cursor = Transaction().cursor

        extra_clause = ''
        account_clause = 'AND a.kind = \'receivable\' '
        sign = 1
        if name in ('tax_amount', 'fee_amount'):
            extra_clause = 'AND '
            extra_clause += 'l.second_origin LIKE '
            extra_clause += '\'coop_account.%s_desc' % name[0:3]
            extra_clause += ',%%\' '
            account_clause = 'AND a.kind != \'receivable\' '
            sign = -1

        cursor.execute('SELECT m.id '
            'FROM account_move_line AS l, account_account AS a '
            ', account_move as m '
            'WHERE a.id = l.account '
                '' + account_clause + 'AND a.active '
                '' + extra_clause + 'AND l.move = m.id '
            'GROUP BY m.id '
            'HAVING (%s * SUM((COALESCE(l.debit, 0) - COALESCE(l.credit, 0))) '
                + clause[1] + ' %s)', [sign] + [Decimal(clause[2] or 0)])
        return [('id', 'in', [x[0] for x in cursor.fetchall()])]

    def get_contract(self, name):
        if not (hasattr(self, 'origin') and self.origin):
            return None
        if not self.origin.__name__ == 'contract.contract':
            return None
        return self.origin.id

    def get_wo_tax_amount(self, name):
        return self.total_amount - self.tax_amount

    def get_wo_fee_amount(self, name):
        return self.wo_tax_amount - self.fee_amount


class MoveLine:
    __name__ = 'account.move.line'

    second_origin = fields.Reference('Second Origin',
        selection='get_second_origin')
    origin_name = fields.Function(fields.Char('Origin Name'),
        'get_origin_name')
    second_origin_name = fields.Function(fields.Char('Second Origin Name'),
        'get_second_origin_name')
    total_amount = fields.Function(
        fields.Numeric('Total amount'),
        'get_total_amount')

    def get_origin_name(self, name):
        if not (hasattr(self, 'origin') and self.origin):
            return ''
        return self.origin.rec_name

    def get_second_origin_name(self, name):
        if not (hasattr(self, 'second_origin') and self.second_origin):
            return ''
        return self.second_origin.rec_name

    def get_total_amount(self, name):
        if self.account.kind == 'receivable':
            return self.debit - self.credit
        return self.credit - self.debit

    @classmethod
    def _get_second_origin(cls):
        return [
            'offered.product',
            'offered.coverage',
            'coop_account.tax_desc',
            'coop_account.fee_desc',
            ]

    @classmethod
    def get_second_origin(cls):
        Model = Pool().get('ir.model')
        models = cls._get_second_origin()
        models = Model.search([
                ('model', 'in', models),
                ])
        return [('', '')] + [(m.model, m.name) for m in models]


class Account:
    __name__ = 'account.account'

    @classmethod
    def _export_skips(cls):
        res = super(Account, cls)._export_skips()
        res.add('left')
        res.add('right')
        return res

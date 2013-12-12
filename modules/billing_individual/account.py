from decimal import Decimal
from sql.aggregate import Sum
from sql.conditionals import Coalesce

from trytond.transaction import Transaction
from trytond.pool import PoolMeta, Pool
from trytond.modules.coop_utils import fields

__metaclass__ = PoolMeta
__all__ = [
    'Move',
    'MoveLine',
]


class Move:
    __name__ = 'account.move'

    billing_period = fields.Many2One('contract.billing.period', 'Billing Period',
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
        fields.Many2One('contract', 'Contract'),
        'get_contract')
    schedule = fields.One2ManyDomain('account.move.line', 'move', 'Schedule',
        domain=[('account.kind', '=', 'receivable')], order=[
            ('maturity_date', 'ASC')])
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
        return super(Move, cls)._get_origin() + ['contract']

    @classmethod
    def get_basic_amount(cls, moves, name):
        res = dict((m.id, Decimal('0.0')) for m in moves)
        cursor = Transaction().cursor

        pool = Pool()
        move_line = pool.get('account.move.line').__table__()
        account = pool.get('account.account').__table__()
        move = pool.get('account.move').__table__()

        query_table = move.join(move_line,
            condition=(move.id == move_line.move)
            ).join(account, condition=(account.id == move_line.account))

        extra_clause = (account.kind == 'receivable')
        sign = 1
        if name in ('tax_amount', 'fee_amount'):
            extra_clause = ((move_line.second_origin.like(
                        'coop_account.%s_desc,%%' % name[0:3]))
                & (account.kind != 'receivable'))
            sign = -1

        cursor.execute(*query_table.select(move.id, Sum(
                    Coalesce(move_line.debit, 0)
                    - Coalesce(move_line.credit, 0)),
                where=(account.active)
                & extra_clause
                & (move.id.in_([m.id for m in moves])),
                group_by=(move.id)))
        for move_id, sum in cursor.fetchall():
            # SQLite uses float for SUM
            if not isinstance(sum, Decimal):
                sum = Decimal(str(sum))
            if sum == 0:
                res[move_id] = sum
            else:
                res[move_id] = sum * sign
        return res

    @classmethod
    def search_basic_amount(cls, name, clause):
        cursor = Transaction().cursor

        _, operator, value = clause
        Operator = fields.SQL_OPERATORS[operator]

        pool = Pool()
        move_line = pool.get('account.move.line').__table__()
        account = pool.get('account.account').__table__()
        move = pool.get('account.move').__table__()

        query_table = move.join(move_line,
            condition=(move.id == move_line.move)
            ).join(account, condition=(account.id == move_line.account))

        extra_clause = (account.kind == 'receivable')
        sign = 1
        if name in ('tax_amount', 'fee_amount'):
            extra_clause = ((move_line.second_origin.like(
                        'coop_account.%s_desc,%%' % name[0:3]))
                & (account.kind != 'receivable'))
            sign = -1

        cursor.execute(*query_table.select(move.id,
                where=(account.active)
                & extra_clause,
                group_by=(move.id),
                having=Operator(sign * Sum(Coalesce(move_line.debit, 0)
                        - Coalesce(move_line.credit, 0)),
                    getattr(cls, name).sql_format(value))))

        return [('id', 'in', [x[0] for x in cursor.fetchall()])]

    def get_contract(self, name):
        if not (hasattr(self, 'origin') and self.origin):
            return None
        if not self.origin.__name__ == 'contract':
            return None
        return self.origin.id

    def get_wo_tax_amount(self, name):
        return self.total_amount - self.tax_amount

    def get_wo_fee_amount(self, name):
        return self.wo_tax_amount - self.fee_amount

    def get_rec_name(self, name):
        if not self.contract:
            return super(Move, self).get_rec_name(name)
        return self.contract.get_rec_name(name)


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

    @classmethod
    def get_payment_amount(cls, lines, name):
        res = super(MoveLine, cls).get_payment_amount(lines, name)
        for k, v in res.iteritems():
            if v < 0:
                res[k] = 0
        return res

    def get_rec_name(self, name):
        return '%.2f - %s' % (
            self.debit - self.credit, self.move.get_rec_name(None))

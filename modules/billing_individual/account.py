import copy
from decimal import Decimal
from sql.aggregate import Sum
from sql.conditionals import Coalesce

from trytond.transaction import Transaction
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval

from trytond.modules.cog_utils import fields, export, model
from trytond.modules.currency_cog import ModelCurrency

__metaclass__ = PoolMeta
__all__ = [
    'MoveComputationLog',
    'MoveBreakdown',
    'Move',
    'MoveLine',
    'TaxDesc',
    'FeeDesc',
    ]


class MoveComputationLog(model.CoopSQL, model.CoopView, ModelCurrency):
    'Move Computation Log'

    __name__ = 'account.move.computation_log'

    move = fields.Many2One('account.move', 'Move', states={'required': True},
        ondelete='CASCADE')
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    origin = fields.Char('Origin')
    base_amount = fields.Char('Base Amount')
    final_amount = fields.Char('Final Amount')
    ratio = fields.Char('Ratio')
    level = fields.Integer('Level', states={'invisible': True})

    def get_currency(self):
        try:
            return self.move.contract.currency
        except:
            return None

    def init_from_log(self, log, work_set):
        self.currency = work_set.move.contract.currency
        self.origin = log['from'].get_rec_name(None)
        self.start_date = log['start_date']
        self.end_date = log['end_date']
        self.base_amount = '%s %s' % (log['base_amount'], self.currency.symbol)
        self.final_amount = '%s %s' % (log['final_amount'],
            self.currency.symbol)
        self.ratio = '%.2f %%' % (log['ratio'] * 100)
        self.move = work_set.move
        if log['from'].__name__ == 'offered.option.description':
            if log['from'].kind == 'insurance':
                self.level = 1
        else:
            self.level = 2


class MoveBreakdown(model.CoopSQL, model.CoopView, ModelCurrency):
    'Move Breakdown'

    __name__ = 'account.move.breakdown'

    move = fields.Many2One('account.move', 'Move', states={'required': True},
        ondelete='CASCADE')
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    total_wo_fees = fields.Numeric('Amount w/o fees')
    fees = fields.Numeric('Fees')
    total_wo_taxes = fields.Numeric('Total HT')
    taxes = fields.Numeric('Taxes')
    total = fields.Numeric('Total')

    def ventilate_amounts(self, work_set):
        ratio = self.total / work_set.total_amount
        self.taxes = work_set.move.tax_amount * ratio
        self.total_wo_taxes = self.total - self.taxes
        self.fees = work_set.move.fee_amount * ratio
        self.total_wo_fees = self.total_wo_taxes - self.fees
        return ratio

    def get_currency(self):
        if not (hasattr(self, 'move') and self.move):
            return None
        if not (hasattr(self.move, 'contract') and self.move.contract):
            return None
        if not (hasattr(self.move.contract, 'currency') and
                self.move.contract.currency):
            return None
        return self.move.contract.currency


class Move:
    __name__ = 'account.move'

    billing_period = fields.Many2One('contract.billing.period',
        'Billing Period', ondelete='RESTRICT')
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
                    ('second_origin', 'like', 'offered.option.description,%'),
                    ('second_origin.kind', '=', 'insurance',
                        'offered.option.description')
                ],
                ('second_origin', 'like', 'offered.product,%')]])
    tax_details = fields.One2ManyDomain('account.move.line', 'move', 'Taxes',
        domain=[('account.kind', '!=', 'receivable'),
                ('second_origin', 'like', 'account.tax.description,%')])
    fee_details = fields.One2ManyDomain('account.move.line', 'move', 'Fees',
        domain=[('account.kind', '!=', 'receivable'),
            ('second_origin', 'like', 'account.fee.description,%')])
    breakdown_details = fields.One2Many('account.move.breakdown',
        'move', 'Breakdown Details', states={'readonly': True})
    calculation_details = fields.One2Many('account.move.computation_log',
        'move', 'Calculation Details')

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
                        'account.%s.description,%%' % name[0:3]))
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
                        'account_cog.%s_desc,%%' % name[0:3]))
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
            'offered.option.description',
            'account.tax.description',
            'account.fee.description',
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


class TaxDesc:
    __name__ = 'account.tax.description'

    account_for_billing = fields.Many2One('account.account',
        'Account for billing', depends=['company'], domain=[
            ('company', '=', Eval('context', {}).get('company'))],
        required=True, ondelete='RESTRICT')
    company = fields.Function(
        fields.Many2One('company.company', 'Company',
            depends=['account_for_billing']),
        'get_company', searcher='search_company')

    @classmethod
    def __setup__(cls):
        super(TaxDesc, cls).__setup__()
        cls.account_for_billing = copy.copy(cls.account_for_billing)
        cls.account_for_billing.domain = export.clean_domain_for_import(
            cls.account_for_billing.domain)

    def get_account_for_billing(self):
        return self.account_for_billing

    def get_company(self, name):
        if not (hasattr(self, 'account_for_billing') and
                self.account_for_billing):
            return None
        return self.account_for_billing.company.id

    @classmethod
    def search_company(cls, name, clause):
        return [(('account_for_billing.company',) + tuple(clause[1:]))]


class FeeDesc:
    __name__ = 'account.fee.description'

    account_for_billing = fields.Many2One('account.account',
        'Account for billing', depends=['company'], domain=[
            ('company', '=', Eval('context', {}).get('company'))],
        required=True, ondelete='RESTRICT')
    company = fields.Function(
        fields.Many2One('company.company', 'Company',
            depends=['account_for_billing']),
        'get_company', searcher='search_company')

    @classmethod
    def __setup__(cls):
        super(FeeDesc, cls).__setup__()
        cls.account_for_billing = copy.copy(cls.account_for_billing)
        cls.account_for_billing.domain = export.clean_domain_for_import(
            cls.account_for_billing.domain)

    def get_account_for_billing(self):
        return self.account_for_billing

    def get_company(self, name):
        if not (hasattr(self, 'account_for_billing') and
                self.account_for_billing):
            return None
        return self.account_for_billing.company.id

    @classmethod
    def search_company(cls, name, clause):
        return [(('account_for_billing.company',) + tuple(clause[1:]))]

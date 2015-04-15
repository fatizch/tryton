from itertools import groupby
from sql import Null
from sql.aggregate import Sum
from sql.conditionals import Coalesce
from sql.operators import Not
from decimal import Decimal

from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval
from trytond.wizard import StateView, Button, StateTransition
from trytond.transaction import Transaction

from trytond.modules.cog_utils import fields, model, utils

__metaclass__ = PoolMeta

__all__ = [
    'MoveLine',
    'PaymentInformationSelection',
    'PaymentInformationModification',
    'PaymentCreation',
    'PaymentCreationStart',
    ]


class MoveLine:
    __name__ = 'account.move.line'

    payment_date = fields.Date('Payment Date',
        states={'invisible': (Eval('account_kind') != 'receivable') &
            (Eval('account_kind') != 'payable')},
        depends=['account_kind'])

    @classmethod
    def __setup__(cls):
        super(MoveLine, cls).__setup__()
        cls._check_modify_exclude.add('payment_date')

    @classmethod
    def payment_outstanding_group_clause(cls, lines, line_table):
        '''
            This method return a part of the where clause use to search for
            existing outstanding amount
        '''
        return (line_table.party == lines[0].party.id)

    @classmethod
    def get_outstanding_amount(cls, lines):
        '''
            Calculate outstanding payment amount receivable or payable
            as of today for a specific account
        '''
        pool = Pool()
        Account = pool.get('account.account')
        MoveLine = pool.get('account.move.line')
        cursor = Transaction().cursor

        line = MoveLine.__table__()
        account = Account.__table__()

        today_where = ((line.maturity_date <= utils.today())
            | (line.maturity_date == Null))
        group_clause = cls.payment_outstanding_group_clause(lines, line)
        kind = lines[0].account.kind
        company_id = lines[0].move.company.id
        cursor.execute(*line.join(account,
                condition=account.id == line.account
                ).select(Sum(Coalesce(line.debit, 0) -
                    Coalesce(line.credit, 0)),
                where=(account.active
                    & (line.reconciliation == Null)
                    & group_clause
                    & (account.company == company_id)
                    & Not(line.id.in_([p.id for p in lines]))
                    & today_where
                    & (line.payment_date == Null)
                    & (account.kind == kind))))
        value = cursor.fetchone()[0] or Decimal(0)
        return value

    @classmethod
    def init_payments(cls, lines, journal):
        payments = []
        outstanding = cls.get_outstanding_amount(lines)
        if lines[0].account.kind == 'receivable' and outstanding > 0:
            outstanding = 0
        elif lines[0].account.kind == 'payable' and outstanding < 0:
            outstanding = 0
        else:
            outstanding = abs(outstanding)
        for line in lines:
            if (line.debit > 0) or (line.credit < 0):
                kind = 'receivable'
            else:
                kind = 'payable'
            if kind == line.account.kind:
                if outstanding >= line.payment_amount:
                    outstanding -= line.payment_amount
                    continue
                amount = line.payment_amount - outstanding
                outstanding = 0
            else:
                # Can't reduce amount if kind are different
                amount = line.payment_amount
            payments.append({
                    'company': line.account.company.id,
                    'kind': kind,
                    'journal': journal.id,
                    'party': line.party.id,
                    'amount': amount,
                    'line': line.id,
                    'date': line.payment_date,
                    'state': 'approved',
                    })
        return payments

    def get_payment_journal(self):
        pool = Pool()
        AccountConfiguration = pool.get('account.configuration')
        account_configuration = AccountConfiguration(1)
        return account_configuration.get_payment_journal(self)

    @classmethod
    def _process_payment_key(cls, line):
        return (line.party, line.get_payment_journal(), line.account.kind)

    @classmethod
    def create_payments(cls, lines):
        pool = Pool()
        Payment = pool.get('account.payment')
        payments = []
        lines = sorted(lines, key=cls._process_payment_key)
        _group_lines = groupby(lines, key=cls._process_payment_key)
        for key, lines in _group_lines:
            payments.extend(cls.init_payments(list(lines), key[1]))
        return Payment.create(payments)


class PaymentInformationSelection(model.CoopView):
    'Payment Information Selection'

    __name__ = 'account.payment.payment_information_selection'

    new_date = fields.Date('New Payment Date')
    move_line = fields.Many2One('account.move.line', 'Move Line')


class PaymentInformationModification(model.CoopWizard):
    'Payment Information Modification'

    __name__ = 'account.payment.payment_information_modification'

    start_state = 'payment_information_selection'
    payment_information_selection = StateView(
        'account.payment.payment_information_selection',
        'account_payment_cog.'
        'payment_information_modification_view_form',
        [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Next', 'finalize', 'tryton-go-next', default=True),
        ])
    finalize = StateTransition()

    def default_payment_information_selection(self, values):
        pool = Pool()
        MoveLine = pool.get('account.move.line')
        cur_model = Transaction().context.get('active_model')
        if cur_model != 'account.move.line':
            raise TypeError
        move_line = MoveLine(Transaction().context.get('active_id'))
        return {
            'new_date': move_line.payment_date,
            'move_line': move_line.id,
            }

    def transition_finalize(self):
        move_line = self.payment_information_selection.move_line
        if (self.payment_information_selection.new_date and
                (self.payment_information_selection.new_date !=
                    move_line.payment_date)):
            move_line.payment_date =\
                self.payment_information_selection.new_date
            move_line.save()
        return 'end'


class PaymentCreationStart(model.CoopView):
    'Payment Creation Start'
    __name__ = 'account.payment.payment_creation.start'


class PaymentCreation(model.CoopWizard):
    'Payment Creation'
    __name__ = 'account.payment.creation'

    start = StateView('account.payment.payment_creation.start',
    'account_payment_cog.payment_creation_start_view_form', [
        Button('Cancel', 'end', 'tryton-cancel'),
        Button('Create Payments', 'create_payments', 'tryton-ok', default=True)
        ])
    create_payments = StateTransition()

    def transition_create_payments(self):
        pool = Pool()
        MoveLine = pool.get('account.move.line')
        active_ids = Transaction().context.get('active_ids')
        lines = MoveLine.search([('id', 'in', active_ids)])
        MoveLine.create_payments(lines)
        return 'end'

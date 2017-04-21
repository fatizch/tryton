# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from itertools import groupby
from sql import Null
from sql.aggregate import Sum
from sql.conditionals import Coalesce
from sql.operators import Not
from decimal import Decimal
from collections import defaultdict

from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, Bool, PYSONEncoder
from trytond.wizard import StateView, Button, StateTransition, StateAction
from trytond.transaction import Transaction
from trytond.modules.account_payment.payment import KINDS
from trytond.modules.coog_core import fields, model, utils

__metaclass__ = PoolMeta

__all__ = [
    'Move',
    'MoveLine',
    'PaymentInformationSelection',
    'PaymentInformationModification',
    'PaymentCreation',
    'PaymentCreationStart',
    ]


class Move:
    __name__ = 'account.move'

    @classmethod
    def __setup__(cls):
        super(Move, cls).__setup__()
        cls.kind.selection.append(
            ('automatic_payment_in', 'Automatic Payment In'))
        cls.kind.selection.append(
            ('automatic_payment_out', 'Automatic Payment Out'))
        cls.kind.selection.append(
            ('rejected_payment_in', 'Rejected Payment In'))
        cls.kind.selection.append(
            ('rejected_payment_out', 'Rejected Payment Out'))

    def get_kind(self, name):
        if self.origin:
            if (self.origin.__name__ == 'account.payment'):
                return ('automatic_payment_in' if self.origin.kind ==
                    'receivable' else 'automatic_payment_out')
            elif (self.origin_item.__name__ == 'account.payment'):
                return ('rejected_payment_in' if self.origin.origin.kind ==
                    'receivable' else 'rejected_payment_out')
        return super(Move, self).get_kind(name)

    def get_icon(self, name):
        if self.kind == 'automatic_payment_in':
            return 'payment_auto_in'
        elif self.kind == 'automatic_payment_out':
            return 'payment_auto_out'
        elif self.kind == 'rejected_payment_in':
            return 'payment_auto_in_cancel'
        elif self.kind == 'rejected_payment_out':
            return 'payment_auto_out_cancel'
        return super(Move, self).get_icon(name)

    def get_synthesis_rec_name(self, name):
        name = super(Move, self).get_synthesis_rec_name(name)
        if (not self.origin_item
                or self.origin_item.__name__ != 'account.payment'):
            return name
        if self.origin_item.state == 'succeeded' and self.description:
            return self.description
        elif self.description:
            return '%s [%s]' % (self.description,
                self.origin_item.state_string)
        else:
            return name

    @classmethod
    def group_moves_for_snapshots(cls, moves):
        if Transaction().context.get('disable_auto_aggregate', False):
            return []
        move_groups = []
        for move_group in super(Move, cls).group_moves_for_snapshots(moves):
            if len(move_group) == 1:
                move_groups.append(move_group)
                continue
            move_group.sort(key=cls.group_for_payment_cancellation)
            for _, group in groupby(move_group,
                    cls.group_for_payment_cancellation):
                move_groups.append(list(group))
        return move_groups

    @classmethod
    def group_for_payment_cancellation(cls, move):
        '''
            Used to find moves which are payment cancellations, since they
            should be merged together when cancelled.
        '''
        if not move.origin:
            return None
        if move.origin.__name__ != 'account.move':
            return None
        if getattr(move.origin.origin, '__name__', '') != 'account.payment':
            return None
        return move.origin.origin.merged_id


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
        cursor = Transaction().connection.cursor()

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

    def new_payment(self, journal, kind, amount):
        return {
            'company': self.account.company.id,
            'kind': kind,
            'journal': journal.id,
            'party': self.party.id,
            'amount': amount,
            'line': self.id,
            'date': self.payment_date,
            'state': 'approved',
            }

    @classmethod
    def init_payments(cls, lines, journal):
        if not lines:
            return []
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
            payments.append(line.new_payment(journal, kind, amount))
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


class PaymentInformationSelection(model.CoogView):
    'Payment Information Selection'

    __name__ = 'account.payment.payment_information_selection'

    new_date = fields.Date('New Payment Date')
    move_lines = fields.Many2Many('account.move.line', None, None,
        'Move Line')


class PaymentInformationModification(model.CoogWizard):
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
        dates = [l.payment_date for l in MoveLine.search(
                [('id', 'in', Transaction().context.get('active_ids'))])]
        date = dates[0] if len(set(dates)) == 1 else None

        return {
            'new_date': date,
            'move_lines': Transaction().context.get('active_ids'),
            }

    def transition_finalize(self):
        lines = []
        new_date = self.payment_information_selection.new_date
        for line in self.payment_information_selection.move_lines:
            if new_date != line.payment_date:
                # Allow to write off existing payment date
                lines.append(line)
        if lines:
            Line = Pool().get('account.move.line')
            Line.write(lines, {'payment_date': new_date})
        return 'end'


class PaymentCreationStart(model.CoogView):
    'Payment Creation Start'
    __name__ = 'account.payment.payment_creation.start'

    party = fields.Many2One('party.party', 'Party', states={
            'invisible': Bool(Eval('multiple_parties')),
            'required': ~Eval('multiple_parties'),
            })
    multiple_parties = fields.Boolean('Payments For Multiple Parties')
    lines_to_pay_filter = fields.Function(
        fields.Many2Many('account.move.line', None, None,
            'Lines To Pay Filter', states={'invisible': True}),
        'on_change_with_lines_to_pay_filter')
    lines_to_pay = fields.Many2Many('account.move.line', None, None,
        'Lines To Pay', required=True, domain=[
            ('id', 'in', Eval('lines_to_pay_filter'))],
        depends=['lines_to_pay_filter'])
    payment_date = fields.Date('Payment Date', states={
            'required': ~Eval('have_lines_payment_date')
             }, help='Payment date is required if at least one line to pay '
        'doesn\'t have a payment date. When its value is set, it is propagated '
        'to all lines to pay.')
    journal = fields.Many2One('account.payment.journal', 'Payment Journal',
        required=True)
    kind = fields.Selection(KINDS, 'Payment Kind')
    process_method = fields.Char('Process Method', states={'invisible': True})
    motive = fields.Many2One('account.payment.motive', 'Motive',
        states={
            'invisible': Bool(Eval('free_motive')),
            'required': ~Eval('free_motive') & ~Eval('multiple_parties') & (
                Eval('kind') == 'payable'),
            }, depends=['free_motive', 'multiple_parties', 'kind'])
    free_motive = fields.Boolean('Free motive')
    description = fields.Char('Description', states={
            'required': ~Eval('multiple_parties') & (Eval('kind') == 'payable'),
            'invisible': ~Eval('free_motive'),
            })
    process_validate_payment = fields.Boolean('Process and Validate Payments',
        states={'invisible': Eval('process_method') != 'manual'},
        depends=['process_method'])
    total_amount = fields.Numeric('Total Amount', readonly=True)
    have_lines_payment_date = fields.Boolean('Lines Have Payment Date')
    created_payments = fields.Many2Many('account.payment', None, None,
        'Created Payments')

    @classmethod
    def view_attributes(cls):
        return super(PaymentCreationStart, cls).view_attributes() + [
            ('/form/group[@id="invisible"]', 'states',
                {'invisible': True}),
            ]

    @fields.depends('party', 'kind')
    def on_change_with_lines_to_pay_filter(self, name=None):
        pool = Pool()
        Line = pool.get('account.move.line')
        Account = Pool().get('account.account')
        if not self.party:
            return []
        accounts = [x.id for x in Account.search(
                [('kind', 'in', ('receivable', 'payable'))])]
        if self.kind == 'receivable':
            sign_clause = ['OR',
                    [('credit', '<', 0)],
                    [('debit', '>', 0)]]
        else:
            sign_clause = ['OR',
                    [('credit', '>', 0)],
                    [('debit', '<', 0)]]
        lines = Line.search([
                ('account', 'in', accounts),
                sign_clause,
                ('party', '=', self.party.id),
                ('reconciliation', '=', None)
                ])
        return [x.id for x in lines if x.payment_amount != 0]

    @fields.depends('journal')
    def on_change_with_process_method(self, name=None):
        return self.journal.process_method if self.journal else ''

    @fields.depends('lines_to_pay', 'kind')
    def on_change_with_total_amount(self, name=None):
        total = sum([(line.credit - line.debit) for line in self.lines_to_pay])
        if self.kind == 'receivable':
            total = -total
        return total

    @fields.depends('motive')
    def on_change_with_description(self):
        return self.motive.name if self.motive else None

    @fields.depends('lines_to_pay', 'payment_date')
    def on_change_lines_to_pay(self):
        self.have_lines_payment_date = all(
            x.payment_date for x in self.lines_to_pay)
        if not self.have_lines_payment_date and self.payment_date is None:
            self.payment_date = utils.today()


class PaymentCreation(model.CoogWizard):
    'Payment Creation'
    __name__ = 'account.payment.creation'

    start = StateView('account.payment.payment_creation.start',
    'account_payment_cog.payment_creation_start_view_form', [
        Button('Cancel', 'end', 'tryton-cancel'),
        Button('Create Payments', 'create_payments', 'tryton-ok', default=True)
        ])
    create_payments = StateTransition()
    created_payments = StateAction('account_payment.act_payment_form')

    @classmethod
    def __setup__(cls):
        super(PaymentCreation, cls).__setup__()
        cls._error_messages.update({
                'incompatible_lines': 'Selected lines are incompatible. Some '
                'are payable lines some are receivable.',
                'incompatible_lines_with_kind': 'Selected lines are '
                'incompatible with selected kind',
                })

    def get_lines_amount_per_kind(self, lines):
        # lines must be same type
        res = defaultdict(lambda: 0)
        for line in lines:
            if (line.debit > 0) or (line.credit < 0):
                res['receivable'] += line.debit - line.credit
            else:
                res['payable'] += line.debit - line.credit
        if len(res) != 1:
            self.raise_user_error('incompatible_lines')
        return res

    def default_start(self, values):
        pool = Pool()
        Line = pool.get('account.move.line')
        Account = pool.get('account.account')
        model = Transaction().context.get('active_model')
        if model == 'account.move.line':
            active_ids = Transaction().context.get('active_ids', [])
            lines = [l for l in Line.browse(active_ids)
                if l.reconciliation is None and l.payment_amount != 0]
            if not lines:
                return {}
            kind = self.get_lines_amount_per_kind(lines)
            parties = list(set([l.party for l in lines]))
            payment_dates = list(set([l.payment_date for l in lines]))
            return {
                'lines_to_pay': active_ids,
                'total_amount': kind.values()[0],
                'kind': kind.keys()[0],
                'multiple_parties': len(parties) != 1,
                'party': parties[0].id if len(parties) == 1 else None,
                'payment_date': (payment_dates[0]
                    if len(payment_dates) == 1 else None),
                }
        elif model == 'party.party':
            active_id = Transaction().context.get('active_id', None)
            accounts = [x.id for x in Account.search(
                    [('kind', 'in', ('receivable', 'payable'))])]
            lines = Line.search([
                    ('account', 'in', accounts),
                    ['OR',
                        [('credit', '>', 0)],
                        [('debit', '<', 0)]],
                    ('party', '=', active_id),
                    ('reconciliation', '=', None)
                    ])
            move_line_ids = [x.id for x in lines if x.payment_amount != 0]
            payment_dates = list(set([l.payment_date for l in lines]))
            return {
                'kind': 'payable',
                'multiple_parties': False,
                'party': active_id,
                'lines_to_pay': move_line_ids,
                'payment_date': (payment_dates[0]
                    if len(payment_dates) == 1 else None),
                }
        return {'kind': 'payable'}

    def init_payment(self, payment):
        if self.start.description:
            payment['description'] = self.start.description

    def transition_create_payments(self):
        pool = Pool()
        MoveLine = pool.get('account.move.line')
        Payment = pool.get('account.payment')

        kind = self.get_lines_amount_per_kind(self.start.lines_to_pay)
        if kind.keys()[0] != self.start.kind:
            self.raise_user_error('incompatible_lines_with_kind')
        if self.start.payment_date:
            MoveLine.write(list(self.start.lines_to_pay),
                {'payment_date': self.start.payment_date})
        payments = MoveLine.init_payments(self.start.lines_to_pay,
            self.start.journal)
        for payment in payments:
            self.init_payment(payment)
        payments = Payment.create(payments)
        if self.start.process_validate_payment:
            def group():
                Group = pool.get('account.payment.group')
                group = Group(journal=self.start.journal.id,
                    kind=self.start.kind)
                group.save()
                return group
            Payment.process(payments, group)
            Payment.succeed(payments)
        action_meth = getattr(self, 'action_%s' % self.start.process_method,
            lambda: 'created_payments')
        Payment.save(payments)
        self.start.created_payments = [x.id for x in payments]
        return action_meth()

    def do_created_payments(self, action):
        encoder = PYSONEncoder()
        payment_ids = [x.id for x in self.start.created_payments]
        action['pyson_domain'] = encoder.encode([('id', 'in', payment_ids)])
        action['pyson_search_value'] = encoder.encode([])
        return action, {'extra_context': {'created_payments': payment_ids}}

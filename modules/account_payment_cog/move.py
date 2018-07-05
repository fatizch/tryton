# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from itertools import groupby
from sql import Null
from sql.aggregate import Sum
from sql.conditionals import Coalesce
from sql.operators import Not
from decimal import Decimal

from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, Bool, PYSONEncoder, Date, If
from trytond.wizard import StateView, Button, StateTransition, StateAction
from trytond.transaction import Transaction
from trytond.modules.account_payment.payment import KINDS
from trytond.modules.coog_core import fields, model, utils


__all__ = [
    'Move',
    'MoveLine',
    'PaymentInformationSelection',
    'PaymentInformationModification',
    'PaymentCreation',
    'PaymentCreationStart',
    ]


class Move:
    __metaclass__ = PoolMeta
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
        if self.origin and self.origin.id >= 0:
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
        if (not self.origin_item or self.origin.id <= 0
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
    __metaclass__ = PoolMeta
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
    def processing_payments_outstanding_amount(cls, lines):
        pool = Pool()
        account = pool.get('account.account').__table__()
        line = pool.get('account.move.line').__table__()
        payment = pool.get('account.payment').__table__()
        kind = lines[0].account.kind
        company_id = lines[0].move.company.id
        query_table = line.join(account, condition=account.id == line.account
            ).join(payment, condition=(payment.line == line.id) &
                (payment.state.in_(['processing', 'approved'])))
        cursor = Transaction().connection.cursor()
        cursor.execute(*query_table.select(
                Sum(Coalesce(line.debit, 0) - Coalesce(line.credit, 0)),
                where=account.active
                & (account.company == company_id)
                & Not(line.id.in_([p.id for p in lines]))
                & cls.payment_outstanding_group_clause(lines, line)
                & (account.kind == kind)
                & (line.reconciliation != Null)
                & (line.payment_date != Null)))

        return cursor.fetchone()[0] or Decimal(0)

    @classmethod
    def unpaid_outstanding_amount(cls, lines):
        pool = Pool()
        cursor = Transaction().connection.cursor()
        account = pool.get('account.account').__table__()
        line = pool.get('account.move.line').__table__()
        kind = lines[0].account.kind
        company_id = lines[0].move.company.id
        query_table = line.join(account, condition=account.id == line.account)
        today_where = ((line.maturity_date <= utils.today())
            | (line.maturity_date == Null))
        cursor.execute(*query_table.select(
                Sum(Coalesce(line.debit, 0) - Coalesce(line.credit, 0)),
                where=account.active
                & (account.company == company_id)
                & Not(line.id.in_([p.id for p in lines]))
                & cls.payment_outstanding_group_clause(lines, line)
                & (account.kind == kind)
                & today_where
                & (line.reconciliation == Null)
                & (line.payment_date == Null)))

        return cursor.fetchone()[0] or Decimal(0)

    @classmethod
    def get_outstanding_amount(cls, lines):
        '''
            Calculate outstanding payment amount receivable or payable
            as of today for a specific account
        '''
        unpaid_amount = cls.unpaid_outstanding_amount(lines)
        processing_amount = cls.processing_payments_outstanding_amount(lines)
        kind = lines[0].account.kind
        inverted_lines = []
        for line in lines:
            if (
                ((line.debit > 0) or (line.credit < 0)) and (kind == 'payable')
                ) or (
                ((line.debit < 0) or (line.credit > 0))
                    and (kind == 'receivable')):
                unpaid_amount += line.debit - line.credit
                inverted_lines.append(line)
        return ([l for l in lines if l not in inverted_lines],
            unpaid_amount - processing_amount)

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
        lines, outstanding = cls.get_outstanding_amount(lines)
        if not lines:
            return []
        if lines[0].account.kind == 'receivable' and outstanding > 0:
            outstanding = 0
        elif lines[0].account.kind == 'payable' and outstanding < 0:
            outstanding = 0
        else:
            outstanding = abs(outstanding)
        for line in lines:
            if line.payment_blocked:
                continue
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
    def get_payment_journals_from_lines(cls, lines):
        return list(set([x.get_payment_journal() for x in lines]))

    @classmethod
    def get_configuration_journals_from_lines(cls, lines):
        return []

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
            Button('Next', 'check', 'tryton-go-next', default=True),
            ])
    check = StateTransition()
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

    def transition_check(self):
        return 'finalize'

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
        'doesn\'t have a payment date, or it is set in the past. When its '
        'value is set, it is propagated to all lines to pay.',
        domain=[If(Bool(Eval('payment_date', False)),
                [('payment_date', '>=', Date())],
                [])])
    journal = fields.Many2One('account.payment.journal', 'Payment Journal',
        required=True, domain=[('id', 'in', Eval('possible_journals'))],
        depends=['possible_journals'])
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
    possible_journals = fields.Many2Many('account.payment.journal',
        None, None, 'Possible Journals', readonly=True)

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
            x.payment_date and x.payment_date >= utils.today()
            for x in self.lines_to_pay)
        if not self.have_lines_payment_date and self.payment_date is None:
            self.payment_date = utils.today()

    @fields.depends('lines_to_pay', 'kind')
    def on_change_with_possible_journals(self, name=None):
        return [x.id for x in Pool().get('account.payment.creation',
                type='wizard').get_possible_journals(self.lines_to_pay,
                self.kind)]


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
                'updating_payment_date': 'The payment date for all payments '
                'will be updated to %(date)s',
                'different_payment_journal': 'The allowed payment journals '
                'for the selected lines are different and do not allow '
                'them to be processed at the same time.'
                })

    def get_lines_amount_per_kind(self, lines):
        # lines must be same type
        if len({l.account for l in lines}) != 1:
            self.raise_user_error('incompatible_lines')
        total = sum([l.debit - l.credit for l in lines])
        key = 'receivable' if total > 0 else 'payable'
        return {key: total}

    @classmethod
    def get_possible_journals(cls, lines, kind=None):
        '''
        There is no payment journal restriction from any configuration
        '''
        return Pool().get('account.payment.journal').search([()])

    @classmethod
    def get_move_lines_from_active_model(cls):
        pool = Pool()
        Line = pool.get('account.move.line')
        Account = pool.get('account.account')
        model = Transaction().context.get('active_model')
        if model == 'account.move.line':
            active_ids = Transaction().context.get('active_ids', [])
            return [l for l in Line.browse(active_ids)
                if l.reconciliation is None and l.payment_amount != 0]
        elif model == 'party.party':
            active_id = Transaction().context.get('active_id', None)
            accounts = [x.id for x in Account.search(
                    [('kind', 'in', ('receivable', 'payable'))])]
            return Line.search([
                    ('account', 'in', accounts),
                    ['OR',
                        [('credit', '>', 0)],
                        [('debit', '<', 0)]],
                    ('party', '=', active_id),
                    ('reconciliation', '=', None)
                    ])
        return []

    @classmethod
    def check_selection(cls, lines=None):
        lines = lines or cls.get_move_lines_from_active_model()
        if not lines:
            return
        Line = Pool().get('account.move.line')
        payment_journals = Line.get_configuration_journals_from_lines(lines)
        if cls.any_journal_not_allowed(lines, payment_journals):
            cls.raise_user_error('different_payment_journal')
        return payment_journals

    @classmethod
    def any_journal_not_allowed(cls, lines, payment_journals):
        allowed_journals = cls.get_possible_journals(lines)
        for payment_journal in payment_journals:
            if payment_journal not in allowed_journals:
                return True
        return False

    def default_start(self, values):
        self.check_selection()
        model = Transaction().context.get('active_model')
        lines = self.get_move_lines_from_active_model()
        possible_journals = self.get_possible_journals(lines)
        res = {
            'kind': 'payable',
            'possible_journals': [x.id for x in possible_journals],
            }
        if model == 'account.move.line':
            if not lines:
                return {}
            Line = Pool().get(model)
            kind = self.get_lines_amount_per_kind(lines)
            parties = list(set([l.party for l in lines]))
            payment_dates = list(set([l.payment_date for l in lines]))
            journals = Line.get_payment_journals_from_lines(lines)
            journal = journals[0] if len(journals) == 1 else None
            res.update({
                    'lines_to_pay': [x.id for x in lines],
                    'total_amount': kind.values()[0],
                    'kind': kind.keys()[0],
                    'multiple_parties': len(parties) != 1,
                    'party': parties[0].id if len(parties) == 1 else None,
                    'payment_date': payment_dates[0]
                    if len(payment_dates) == 1 else None,
                    'journal': journal.id if journal else None
                    if len(lines) == 1 else None,
                    })
            return res
        elif model == 'party.party':
            active_id = Transaction().context.get('active_id', None)
            move_line_ids = [x.id for x in lines if x.payment_amount != 0]
            payment_dates = list(set([l.payment_date for l in lines]))
            res.update({
                    'kind': 'payable',
                    'multiple_parties': False,
                    'party': active_id,
                    'lines_to_pay': move_line_ids,
                    'payment_date': payment_dates[0]
                    if len(payment_dates) == 1 else None,
                    })
        return res

    def init_payment(self, payment):
        if self.start.description:
            payment['description'] = self.start.description

    def transition_create_payments(self):
        pool = Pool()
        MoveLine = pool.get('account.move.line')
        Payment = pool.get('account.payment')

        payment_journals = MoveLine.get_configuration_journals_from_lines(
            self.start.lines_to_pay)
        if self.any_journal_not_allowed(self.start.lines_to_pay,
                payment_journals):
            self.raise_user_error('different_payment_journal')
        kind = self.get_lines_amount_per_kind(self.start.lines_to_pay)
        if kind.keys()[0] != self.start.kind:
            self.raise_user_error('incompatible_lines_with_kind')
        payment_date = self.start.payment_date or utils.today()
        if any(x.payment_date != payment_date
                for x in self.start.lines_to_pay):
            self.raise_user_warning('updating_payment_date_%s' %
                str(self.start.lines_to_pay[0]), 'updating_payment_date',
                {'date': str(payment_date)})
            MoveLine.write(list(self.start.lines_to_pay),
                {'payment_date': payment_date})
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

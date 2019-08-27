# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from itertools import groupby
from sql import Null, Literal
from sql.aggregate import Sum
from sql.conditionals import Coalesce, Case
from sql.operators import Not
from sql.functions import Abs
from decimal import Decimal

from trytond.exceptions import UserWarning
from trytond.i18n import gettext
from trytond.model.exceptions import ValidationError
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, Bool, PYSONEncoder, Date, If
from trytond.wizard import StateView, Button, StateTransition, StateAction
from trytond.transaction import Transaction
from trytond.modules.account_payment.payment import KINDS
from trytond.modules.coog_core import fields, model, utils
from trytond.modules.currency_cog import ModelCurrency


__all__ = [
    'Move',
    'MoveLine',
    'PaymentInformationSelection',
    'PaymentInformationModification',
    'PaymentCreation',
    'PaymentCreationStart',
    'Reconciliation',
    ]


class Move(metaclass=PoolMeta):
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


class MoveLine(metaclass=PoolMeta):
    __name__ = 'account.move.line'

    payment_date = fields.Date('Payment Date',
        states={'invisible': (~Eval('account.type.receivable')) &
            (~Eval('account.type.payable'))},
        depends=['account'])

    @classmethod
    def __setup__(cls):
        super(MoveLine, cls).__setup__()
        cls._check_modify_exclude.add('payment_date')

        # Change methods in order to avoid tryton overrides
        cls.payment_amount.getter = 'getter_payment_amount'
        cls.payment_amount.searcher = 'searcher_payment_amount'

    # Full override of payment_amount methods in order to fix #7873
    @classmethod
    def getter_payment_amount(cls, instances, clause):
        cursor = Transaction().connection.cursor()

        tables = cls._search_payment_amount_tables()
        join = cls._search_payment_amount_join(tables)
        group_expr = cls._search_payment_amount_group_by(tables)
        amount_expr = cls._search_payment_amount_amount(tables)

        move_line = tables['move_line']
        account_type = tables['account_type']

        result = {x.id: Decimal(0) for x in instances}
        cursor.execute(*join.select(move_line.id, amount_expr,
                where=((account_type.payable == Literal(True))
                    | (account_type.receivable == Literal(True)))
                & move_line.id.in_([x.id for x in instances]),
                group_by=group_expr))

        for line, amount in cursor.fetchall():
            # SQLite uses float for SUM
            if not isinstance(amount, Decimal):
                amount = Decimal(str(amount))
            result[line] = amount
        return result

    @classmethod
    def searcher_payment_amount(cls, name, clause):
        _, operator, value = clause
        Operator = fields.SQL_OPERATORS[operator]
        value = cls.payment_amount.sql_format(value)

        tables = cls._search_payment_amount_tables()
        join = cls._search_payment_amount_join(tables)
        group_expr = cls._search_payment_amount_group_by(tables)
        amount_expr = cls._search_payment_amount_amount(tables)

        move_line = tables['move_line']
        account_type = tables['account_type']
        query = join.select(move_line.id,
            where=((account_type.payable == Literal(True))
                | (account_type.receivable == Literal(True))),
            group_by=group_expr,
            having=Operator(amount_expr, value))
        return [('id', 'in', query)]

    @classmethod
    def _search_payment_amount_tables(cls):
        pool = Pool()
        return {
            'move_line': cls.__table__(),
            'payment': pool.get('account.payment').__table__(),
            'account': pool.get('account.account').__table__(),
            'account_type': pool.get('account.account.type').__table__(),
            }

    @classmethod
    def _search_payment_amount_join(cls, tables):
        move_line = tables['move_line']
        payment = tables['payment']
        account = tables['account']
        account_type = tables['account_type']

        return move_line.join(payment, type_='LEFT',
            condition=((move_line.id == payment.line)
                & (payment.state != 'failed'))
            ).join(account, condition=move_line.account == account.id
                ).join(account_type, condition=account.type == account_type.id)

    @classmethod
    def _search_payment_amount_group_by(cls, tables):
        move_line = tables['move_line']

        return (move_line.id, move_line.second_currency)

    @classmethod
    def _search_payment_amount_amount(cls, tables):
        move_line = tables['move_line']
        payment = tables['payment']

        payment_amount = Sum(Coalesce(payment.amount, 0))
        main_amount = Abs(move_line.credit - move_line.debit) - payment_amount
        second_amount = Abs(move_line.amount_second_currency) - payment_amount
        amount = Case((move_line.reconciliation != Null, 0),
            (move_line.second_currency == Null, main_amount),
            else_=second_amount)

        return amount
    # End of override

    @classmethod
    def payment_outstanding_group_clause(cls, lines, line_table):
        '''
            This method return a part of the where clause use to search for
            existing outstanding amount
        '''
        return (line_table.party == lines[0].party.id)

    @classmethod
    def outstanding_amount(cls, lines, processing_payments=False):
        if not lines:
            return [], Decimal(0)
        pool = Pool()
        cursor = Transaction().connection.cursor()
        account = pool.get('account.account').__table__()
        line = pool.get('account.move.line').__table__()
        payment = pool.get('account.payment').__table__()
        company_id = lines[0].move.company.id
        account_id = lines[0].account.id
        query_table = line.join(account, condition=account.id == line.account)
        if processing_payments:
            query_table = query_table.join(payment,
                condition=(payment.line == line.id) &
                (payment.state.in_(['processing', 'approved'])))
            where_clause = ((line.reconciliation != Null)
                & (line.payment_date != Null))
            sign = -1
        else:
            where_clause = (
                ((line.maturity_date <= utils.today())
                    | (line.maturity_date == Null))
                & (line.reconciliation == Null) & (line.payment_date == Null)
                & Not(line.id.in_([p.id for p in lines])))
            sign = 1

        cursor.execute(*query_table.select(line.id,
                where=(account.company == company_id)
                & cls.payment_outstanding_group_clause(lines, line)
                & (account.id == account_id)
                & (line.payment_blocked == Literal(False))
                & where_clause))
        ids = [x[0] for x in cursor.fetchall()]
        if ids:
            cursor.execute(*line.select(
                    Sum(Coalesce(line.debit, 0) - Coalesce(line.credit, 0)),
                    where=line.id.in_(ids)))
            outstanding = cursor.fetchone()[0] * sign or 0
        else:
            outstanding = 0
        global_kind = cls.get_kind(lines)
        if (global_kind == 'receivable' and outstanding > 0) or (
                global_kind == 'payable' and outstanding < 0):
            outstanding = 0
        if outstanding:
            return ids, outstanding
        else:
            return [], Decimal(0)

    @classmethod
    def calculate_amount(cls, lines, ignore_unpaid_lines=False):
        if len({l.account for l in lines}) > 1:
            raise ValidationError(gettext(
                    'account_payment_cog.msg_incompatible_lines'))
        unpaid_amount = 0
        if not ignore_unpaid_lines:
            _, unpaid_amount = cls.outstanding_amount(lines)
        _, processing_amount = cls.outstanding_amount(lines, True)
        kind = cls.get_kind(lines)
        inverted_lines = []
        for line in [l for l in lines if cls.get_kind([l]) != kind]:
            unpaid_amount += cls.get_sum([line])
            inverted_lines.append(line)
        return ([l for l in lines if l not in inverted_lines],
            unpaid_amount - processing_amount)

    @classmethod
    def get_sum(cls, lines):
        return sum([l.debit - l.credit for l in lines])

    @classmethod
    def get_kind(cls, lines, amount=0):
        return 'receivable' if (cls.get_sum(lines) + amount) > 0 else 'payable'

    def new_payment(self, journal, kind, amount):
        return {
            'company': self.account.company.id,
            'kind': kind,
            'journal': journal.id,
            'party': self.party.id,
            'amount': amount,
            'line': self.id,
            'date': self.payment_date or utils.today(),
            'state': 'approved',
            }

    @classmethod
    def init_payments(cls, lines, journal, ignore_unpaid_lines=False):
        if not lines:
            return []
        payments = []
        lines, outstanding = cls.calculate_amount(lines, ignore_unpaid_lines)
        if not lines:
            return []
        outstanding = abs(outstanding)
        for line in lines:
            if line.payment_blocked:
                continue
            if outstanding >= line.payment_amount:
                outstanding -= line.payment_amount
                continue
            amount = line.payment_amount - outstanding
            outstanding = 0
            if amount:
                payments.append(line.new_payment(journal, cls.get_kind(lines),
                    amount))
        return payments

    def get_payment_journal(self):
        pool = Pool()
        AccountConfiguration = pool.get('account.configuration')
        account_configuration = AccountConfiguration(1)
        return account_configuration.get_payment_journal(self)

    @classmethod
    def get_payment_journals_from_lines(cls, lines):
        return [y for y in set([x.get_payment_journal() for x in lines]) if y]

    @classmethod
    def get_configuration_journals_from_lines(cls, lines):
        return []

    @classmethod
    def _process_payment_key(cls, line):
        return (line.party or -1, line.get_payment_journal() or -1,
            line.account)

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


class PaymentCreationStart(model.CoogView, ModelCurrency):
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
    total_amount = fields.Numeric('Total Amount', readonly=True,
        digits=(16, Eval('currency_digits', 2)), depends=['currency_digits'])
    have_lines_payment_date = fields.Boolean('Lines Have Payment Date')
    created_payments = fields.Many2Many('account.payment', None, None,
        'Created Payments')
    possible_journals = fields.Many2Many('account.payment.journal',
        None, None, 'Possible Journals', readonly=True)
    unpaid_outstanding_lines = fields.Many2Many('account.move.line', None, None,
        'Unpaid Outstanding Lines', readonly=True,
        states={'invisible': ~Eval('unpaid_outstanding_lines')
            | Bool(Eval('ignore_unpaid_lines'))})
    ignore_unpaid_lines = fields.Boolean('Ignore Unpaid Lines',
        states={'invisible': ~Eval('unpaid_outstanding_lines')},
        depends=['unpaid_outstanding_lines'])
    lines_with_processing_payments = fields.Many2Many('account.move.line', None,
         None, 'Lines with Processing Payments', readonly=True,
        states={'invisible': ~Eval('lines_with_processing_payments')})

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
                ['OR',
                    ('type.receivable', '=', True),
                    ('type.payable', '=', True),
                    ])]
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

    @fields.depends('motive')
    def on_change_with_description(self):
        return self.motive.name if self.motive else None

    def refresh_total_amount(self):
        Line = Pool().get('account.move.line')
        if len({l.account for l in self.lines_to_pay}) > 1:
            raise ValidationError(gettext(
                    'account_payment_cog.msg_incompatible_lines'))
        self.unpaid_outstanding_lines, outstanding_1 = \
            Line.outstanding_amount(self.lines_to_pay)
        if self.ignore_unpaid_lines:
            outstanding_1 = 0
        self.lines_with_processing_payments, outstanding_2 = \
            Line.outstanding_amount(self.lines_to_pay, True)
        self.kind = Line.get_kind(self.lines_to_pay,
            outstanding_1 + outstanding_2)
        self.total_amount = (Line.get_sum(self.lines_to_pay)
            + outstanding_1 + outstanding_2) * (
            -1 if self.kind == 'payable' else 1)

    @fields.depends('lines_to_pay', 'payment_date', 'total_amount', 'kind',
            'ignore_unpaid_lines')
    def on_change_lines_to_pay(self):
        self.have_lines_payment_date = all(
            x.payment_date and x.payment_date >= utils.today()
            for x in self.lines_to_pay)
        if not self.have_lines_payment_date and self.payment_date is None:
            self.payment_date = utils.today()
        self.refresh_total_amount()

    @fields.depends('lines_to_pay', 'ignore_unpaid_lines')
    def on_change_ignore_unpaid_lines(self):
        self.refresh_total_amount()

    @fields.depends('lines_to_pay', 'kind')
    def on_change_with_possible_journals(self, name=None):
        return [x.id for x in Pool().get('account.payment.creation',
                type='wizard').get_possible_journals(self.lines_to_pay,
                self.kind)]

    def get_currency(self, name=None):
        return self.journal.currency if self.journal else None


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
                    ['OR',
                        ('type.receivable', '=', True),
                        ('type.payable', '=', True),
                        ])]
            return Line.search([
                    ('account', 'in', accounts),
                    ('party', '=', active_id),
                    ('reconciliation', '=', None)
                    ])
        elif model == 'account.invoice':
            invoice = Pool().get(model)(Transaction().context.get('active_id'))
            return list(invoice.lines_to_pay)
        return []

    @classmethod
    def check_selection(cls, lines=None):
        lines = lines or cls.get_move_lines_from_active_model()
        if not lines:
            return
        Line = Pool().get('account.move.line')
        payment_journals = Line.get_configuration_journals_from_lines(lines)
        if cls.any_journal_not_allowed(lines, payment_journals):
            raise ValidationError(gettext(
                    'account_payment_cog.msg_different_payment_journal'))
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
        if not lines:
            if model in ('account.invoice', 'party.party') and not lines:
                raise ValidationError(gettext(
                        'account_payment_cog.msg_nothing_to_pay'))
            return {}
        possible_journals = self.get_possible_journals(lines)
        Line = Pool().get('account.move.line')
        parties = list(set([l.party for l in lines]))
        payment_dates = list(set([l.payment_date for l in lines]))
        journals = Line.get_payment_journals_from_lines(lines)
        journal = None

        if len(lines) == 1 and len(journals) == 1:
            journal = journals[0].id
        return {
            'possible_journals': [x.id for x in possible_journals],
            'lines_to_pay': [x.id for x in lines],
            'multiple_parties': len(parties) != 1,
            'party': parties[0].id if len(parties) == 1 else None,
            'payment_date': payment_dates[0]
            if len(payment_dates) == 1 else None,
            'journal': journal,
            }

    def init_payment(self, payment):
        if self.start.description:
            payment['description'] = self.start.description

    def transition_create_payments(self):
        pool = Pool()
        MoveLine = pool.get('account.move.line')
        Payment = pool.get('account.payment')
        Warning = pool.get('res.user.warning')

        payment_journals = MoveLine.get_configuration_journals_from_lines(
            self.start.lines_to_pay)
        if self.any_journal_not_allowed(self.start.lines_to_pay,
                payment_journals):
            raise ValidationError(gettext(
                    'account_payment_cog.msg_different_payment_journal'))
        kind = MoveLine.get_kind(self.start.lines_to_pay)
        if kind != self.start.kind:
            raise ValidationError(gettext(
                    'account_payment_cog.msg_incompatible_lines_with_kind'))
        payment_date = self.start.payment_date or utils.today()

        # In the case we mix lines from different kind, we should not update
        # the payment date for lines with a kind different as the global kind
        lines_to_update = [l for l in self.start.lines_to_pay
            if MoveLine.get_kind([l]) == kind]
        if any(x.payment_date != payment_date for x in lines_to_update):
            key = 'updating_payment_date_%s' % str(lines_to_update[0])
            if Warning.check(key):
                raise UserWarning(key, gettext(
                        'account_payment_cog.msg_updating_payment_date',
                        date=str(payment_date)))
            MoveLine.write(lines_to_update, {'payment_date': payment_date})

        payments = MoveLine.init_payments(self.start.lines_to_pay,
            self.start.journal, self.start.ignore_unpaid_lines)
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


class Reconciliation(metaclass=PoolMeta):
    __name__ = 'account.move.reconciliation'

    @classmethod
    def delete(cls, reconciliations):
        MoveLine = Pool().get('account.move.line')
        lines_to_clear = []
        for reconciliation in reconciliations:
            for line in reconciliation.lines:
                if line.payment_date and all(
                        [x.needs_to_clear_payment_date_after_failure()
                            for x in line.payments]):
                    lines_to_clear.append(line)
        super(Reconciliation, cls).delete(reconciliations)
        MoveLine.write(lines_to_clear, {'payment_date': None})

# -*- coding:utf-8 -*-
from collections import defaultdict
from itertools import groupby
from sql.aggregate import Sum, Max
from sql import Literal, Null

from trytond import backend
from trytond.transaction import Transaction
from trytond.model import ModelView, Unique
from trytond.wizard import StateView, Button, StateTransition, Wizard
from trytond.wizard import StateAction
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, Not, In, Bool, If, PYSONEncoder

from trytond.modules.cog_utils import export, fields, model
from trytond.modules.cog_utils import coop_date, utils, coop_string
from trytond.modules.report_engine import Printable
from trytond.modules.currency_cog import ModelCurrency

__metaclass__ = PoolMeta

__all__ = [
    'Payment',
    'MergedPayments',
    'FilterPaymentsPerMergedId',
    'Configuration',
    'Journal',
    'JournalFailureAction',
    'RejectReason',
    'Group',
    'PaymentFailInformation',
    'ManualPaymentFail',
    'PaymentMotive',
    'ProcessManualFailPament',
    ]


class Journal(export.ExportImportMixin):
    __name__ = 'account.payment.journal'
    _func_key = 'name'

    failure_actions = fields.One2Many('account.payment.journal.failure_action',
        'journal', 'Failure Actions',
        context={'default_fee_id': Eval('default_reject_fee')},
        depends=['default_reject_fee'])
    default_reject_fee = fields.Many2One('account.fee',
        'Default Fee', ondelete='RESTRICT')

    def get_fail_actions(self, payments):
        """
            Payments is a list of payments processed in the same payment
            transaction
        """
        reject_code = payments[0].fail_code
        payment_reject_number = max(len(payment.line.payments) for payment in
            payments)
        possible_actions = [action for action in self.failure_actions
            if action.reject_reason.code == reject_code]
        possible_actions.sort(key=lambda x: x.reject_number, reverse=True)
        for action in possible_actions:
            if (not action.reject_number or
                    action.reject_number == payment_reject_number):
                actions = [(action.action, )]
                if action.report_template:
                    actions.append(('print', action.report_template))
                return actions
        return [('manual',)]

    @classmethod
    def _export_light(cls):
        return super(Journal, cls)._export_light() | {'currency', 'company',
            'default_reject_fee'}

    def get_next_possible_payment_date(self, line, day):
        return coop_date.get_next_date_in_sync_with(
            max(line['maturity_date'], utils.today()), day)


class JournalFailureAction(model.CoopSQL, model.CoopView):
    'Journal Failure Action'

    __name__ = 'account.payment.journal.failure_action'
    _rec_name = 'reject_reason'
    _func_key = 'func_key'

    reject_reason = fields.Many2One('account.payment.journal.reject_reason',
        'Reject Reason', required=True, ondelete='RESTRICT')
    journal = fields.Many2One('account.payment.journal', 'Journal',
        required=True, ondelete='CASCADE', select=True)
    action = fields.Selection([
            ('manual', 'Manual'),
            ('retry', 'Retry'),
            ], 'Action')
    rejected_payment_fee = fields.Many2One('account.fee',
        'Fee', ondelete='RESTRICT')
    is_fee_required = fields.Function(fields.Boolean('Fee Required'),
        'on_change_with_is_fee_required', setter='setter_void')
    reject_number = fields.Integer('Reject Number', help='Filter the action '
        'according to the number of rejects for a given payment. If empty, '
        'action will be used for all rejects')
    func_key = fields.Function(fields.Char('Functional Key'),
        'get_func_key', searcher='search_func_key')
    report_template = fields.Many2One('report.template', 'Report Template',
        domain=[('kind', '=', 'reject_payment')],
        ondelete='RESTRICT')

    @classmethod
    def __register__(cls, module_name):
        # Migration from 1.3: Drop code_unique constraint
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().cursor
        table = TableHandler(cursor, cls, module_name)
        table.drop_constraint('code_unique')
        super(JournalFailureAction, cls).__register__(module_name)

    @classmethod
    def __setup__(cls):
        super(JournalFailureAction, cls).__setup__()
        cls._error_messages.update({
                'unknown_reject_reason_code': 'Unknown reject code : %s',
                })

    @classmethod
    def _export_light(cls):
        return super(JournalFailureAction, cls)._export_light() | {
            'reject_reason', 'rejected_payment_fee', 'report_template'}

    @classmethod
    def get_rejected_payment_fee(cls, code):
        if not code:
            return
        JournalFailureAction = Pool().get(
            'account.payment.journal.failure_action')
        failure_actions = JournalFailureAction.search([
                ('reject_reason.code', '=', code)
                ])
        if len(failure_actions) == 0:
            cls.raise_user_error('unknown_reject_reason_code', (code))
        failure_action = failure_actions[0]
        return failure_action.rejected_payment_fee

    @fields.depends('rejected_payment_fee')
    def on_change_with_is_fee_required(self, name=None):
        return self.rejected_payment_fee is not None

    @fields.depends('is_fee_required', 'rejected_payment_fee')
    def on_change_is_fee_required(self):
        if not self.is_fee_required:
            self.rejected_payment_fee = None
        else:
            self.rejected_payment_fee = Transaction().context.get(
                'default_fee_id', None)

    def get_func_key(self, name):
        return '%s|%s|%s' % (self.journal.name, self.reject_reason.code,
            self.reject_number)

    @classmethod
    def search_func_key(cls, name, clause):
        assert clause[1] == '='
        if '|' in clause[2]:
            operands = clause[2].split('|')
            if len(operands) == 3:
                journal_name, reject_reason_code, number = clause[2].split('|')
                return [('journal.name', clause[1], journal_name),
                    ('reject_reason.code', clause[1], reject_reason_code),
                    ('reject_number', clause[1], number)]
            else:
                return [('id', '=', None)]
        else:
            return ['OR',
                [('journal.name',) + tuple(clause[1:])],
                [('reject_reason.code',) + tuple(clause[1:])],
                ]


class RejectReason(model.CoopSQL, model.CoopView):
    'Payment Journal Reject Reason'
    __name__ = 'account.payment.journal.reject_reason'
    _func_key = 'code'

    code = fields.Char('Code', required=True)
    description = fields.Char('Description', required=True, translate=True)
    process_method = fields.Char('Process method', required=True)

    @classmethod
    def __setup__(cls):
        super(RejectReason, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('code_unique', Unique(t, t.code), 'The code must be unique'),
            ]
        cls._order = [('process_method', 'ASC'), ('code', 'ASC')]

    @classmethod
    def is_master_object(cls):
        return True

    def get_rec_name(self, name):
        return '[%s] %s' % (self.code, self.description)

    @classmethod
    def search_rec_name(cls, name, clause):
        return ['OR',
            ('code',) + tuple(clause[1:]),
            ('description',) + tuple(clause[1:])
            ]


class FilterPaymentsPerMergedId(Wizard):
    'Filter Payments per cheque'

    __name__ = 'account.payment.merged.open_detail'

    start_state = 'filter_payments'
    filter_payments = StateAction('account_payment.act_payment_form')

    def do_filter_payments(self, action):
        # The following active_id represents the max payment id and the
        # intermediate sql-view object id.
        payment = Pool().get('account.payment')(
            Transaction().context.get('active_id'))
        merged_id = payment.merged_id

        domain = [('merged_id', '=', merged_id)]
        action.update({'pyson_domain': PYSONEncoder().encode(domain)})
        action.update({'sequence': 40})
        return action, {}


class MergedPayments(model.CoopSQL, model.CoopView, ModelCurrency,
                     Printable):
    'Merged payments'

    __name__ = 'account.payment.merged'

    merged_id = fields.Char('Merged id', readonly=True)
    amount = fields.Numeric('Amount', readonly=True,
        digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits'])
    journal = fields.Many2One('account.payment.journal', 'Journal',
        readonly=True)
    party = fields.Many2One('party.party', 'Party', readonly=True)
    state = fields.Selection([
            ('draft', 'Draft'),
            ('approved', 'Approved'),
            ('processing', 'Processing'),
            ('succeeded', 'Succeeded'),
            ('failed', 'Failed'),
            ], 'State', readonly=True)

    @classmethod
    def __setup__(cls):
        super(MergedPayments, cls).__setup__()
        cls._order = [('merged_id', 'DESC')]

    def get_currency(self, name=None):
        return self.journal.currency if self.journal else None

    def get_contact(self):
        return self.party

    def get_sender(self):
        return self.journal.company.party

    @staticmethod
    def table_query():
        pool = Pool()
        payment = pool.get('account.payment').__table__()

        return payment.select(
            Max(payment.id).as_('id'),
            payment.merged_id.as_('merged_id'),
            payment.journal.as_('journal'),
            payment.party.as_('party'),
            payment.state.as_('state'),
            Literal(0).as_('create_uid'),
            Literal(0).as_('create_date'),
            Literal(0).as_('write_uid'),
            Literal(0).as_('write_date'),
            Sum(payment.amount).as_('amount'),
            where=(payment.merged_id != Null),
            group_by=[payment.merged_id, payment.journal,
                      payment.party, payment.state])


class Payment(export.ExportImportMixin, Printable):
    __name__ = 'account.payment'
    _func_key = 'id'

    icon = fields.Function(
        fields.Char('Icon'),
        'get_icon')
    manual_fail_status = fields.Selection([
        ('', ''),
        ('pending', 'Pending'),
        ('done', 'Done')
        ], 'Manual Fail Status', states={
            'invisible': ~Bool(Eval('manual_fail_status'))})
    reject_description = fields.Function(
        fields.Char('Reject Description', states={
                'invisible': ~Eval('reject_description')}),
        'get_reject_description')
    merged_id = fields.Char('Merged ID', select=True)

    @classmethod
    def __register__(cls, module_name):
        # Migration from 1.6: Renaming column
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().cursor
        payment_h = TableHandler(cursor, cls, module_name)

        if payment_h.column_exist('sepa_merged_id'):
            payment_h.column_rename('sepa_merged_id', 'merged_id')
        super(Payment, cls).__register__(module_name)

    def get_reject_description(self, name):
        pool = Pool()
        RejectReason = pool.get('account.payment.journal.reject_reason')
        if not self.fail_code:
            return ''
        reject_reason, = RejectReason.search([('code', '=', self.fail_code)])
        return reject_reason.description

    @classmethod
    def __setup__(cls):
        super(Payment, cls).__setup__()
        cls.line.select = True
        cls._error_messages.update({
                'payments_blocked_for_party': 'Payments blocked for party %s',
                'missing_payments': 'Payments with same merged_id must '
                'be failed at the same time.',
                })
        cls._buttons.update({
                'button_fail_payments': {
                    'invisible': Not(In(Eval('state'),
                            ['processing', 'succeeded'])),
                    'icon': 'tryton-cancel',
                },
                'process_payments': {
                    'invisible': Eval('state') != 'approved',
                    'icon': 'tryton-go-next'
                },
                'button_process_fail_payments': {
                    'invisible': Eval('manual_fail_status') != 'pending',
                    'icon': 'tryton-go-next'
                }
        })
        cls.state_string = cls.state.translated('state')

    def get_icon(self, name=None):
        return 'payment'

    def get_synthesis_rec_name(self, name):
        Date = Pool().get('ir.date')
        if self.date and self.state == 'succeeded':
            return '%s - %s - %s' % (self.journal.rec_name,
                Date.date_as_string(self.date),
                self.currency.amount_as_string(self.amount))
        elif self.date:
            return '%s - %s - %s - [%s]' % (self.journal.rec_name,
                Date.date_as_string(self.date),
                self.currency.amount_as_string(self.amount),
                self.state_string)
        else:
            return '%s - %s - [%s]' % (
                Date.date_as_string(self.date),
                self.currency.amount_as_string(self.amount),
                self.state_string)

    def _get_transaction_key(self):
        """
            Return the key to identify payments processed in one transaction
            Overriden in account_payment_sepa_cog
        """
        return (self, self.journal)

    @classmethod
    @model.CoopView.button_action(
        'account_payment_cog.act_process_payments_button')
    def process_payments(cls, payments):
        pass

    @property
    def fail_code(self):
        pass

    @classmethod
    def fail(cls, payments):
        pool = Pool()
        Line = pool.get('account.move.line')
        Event = pool.get('event')
        super(Payment, cls).fail(payments)
        Event.notify_events(payments, 'fail_payment')

        # Remove payment_date on payment line
        lines = [payment.line for payment in payments
            if payment.line is not None]
        Line.write(lines, {'payment_date': None})

        actions = defaultdict(list)
        payments_keys = [(x._get_transaction_key(), x) for x in payments]
        payments_keys = sorted(payments_keys, key=lambda x: x[0])
        for key, payments in groupby(payments_keys, key=lambda x: x[0]):
            payments_list = [payment[1] for payment in payments]
            reject_actions = key[1].get_fail_actions(payments_list)
            for action in reject_actions:
                if action[0] == 'print':
                    actions['fail_print'].extend([(action[1],
                        payments_list)])
                else:
                    actions['fail_%s' % action[0]].extend(payments_list)

        for action, payments in actions.iteritems():
            if action == 'fail_print':
                # treat print at the end once all action are done
                continue
            getattr(cls, action)(payments)
        if 'fail_print' in actions:
            getattr(cls, 'fail_print')(actions['fail_print'])

    @classmethod
    def fail_manual(cls, payments):
        cls.write(payments, {
                'manual_fail_status': 'pending',
                })

    @classmethod
    def fail_retry(cls, payments):
        pass

    @classmethod
    def fail_print(cls, to_prints):
        for report, payments in to_prints:
            report.produce_reports(payments)

    @fields.depends('line')
    def on_change_line(self):
        super(Payment, self).on_change_line()
        if self.line:
            self.date = self.line.payment_date

    @classmethod
    def is_master_object(cls):
        return True

    def get_description(self, lang=None):
        return self.description

    @classmethod
    def approve(cls, payments):
        for payment in payments:
            if (payment.kind == 'payable'
                    and payment.party.block_payable_payments):
                cls.raise_user_error(
                    'payments_blocked_for_party', payment.party.rec_name)
        super(Payment, cls).approve(payments)

    @classmethod
    def process(cls, payments, group):
        pool = Pool()
        Event = pool.get('event')
        group = super(Payment, cls).process(payments, group)
        to_write = []
        for payment in payments:
            description = payment.get_description()
            if description != payment.description:
                to_write += [[payment], {'description': description}]
        if to_write:
            cls.write(*to_write)
        Event.notify_events(payments, 'process_payment')
        return group

    @classmethod
    def succeed(cls, payments):
        pool = Pool()
        Event = pool.get('event')
        super(Payment, cls).succeed(payments)
        Event.notify_events(payments, 'succeed_payment')

    def get_doc_template_kind(self):
        return 'reject_payment'

    def get_contact(self):
        return self.party

    def get_sender(self):
        return self.company.party

    @classmethod
    def payments_fields_to_update_after_fail(cls, reject_reason):
        return {}

    def get_grouping_key(self):
        return self.merged_id if self.merged_id else self.id

    @classmethod
    def manual_set_reject_reason(cls, payments, reject_reason):
        merged_ids = set([p.merged_id for p in payments if p.merged_id])
        if merged_ids:
            all_payments = cls.search([
                    ('merged_id', 'in', merged_ids)])
            if len(all_payments) != len(
                    [x for x in payments if x.merged_id]):
                cls.raise_user_error('missing_payments')
        fields = cls.payments_fields_to_update_after_fail(reject_reason)
        cls.write(payments, fields)

    @classmethod
    @ModelView.button_action('account_payment_cog.manual_payment_fail_wizard')
    def button_fail_payments(cls, payments):
        pass

    @classmethod
    @ModelView.button_action(
        'account_payment_cog.process_manual_payment_fail_wizard')
    def button_process_fail_payments(cls, payments):
        pass


class Configuration:
    __name__ = 'account.configuration'

    direct_debit_journal = fields.Property(
        fields.Many2One('account.payment.journal', 'Direct Debit Journal',
            domain=[('process_method', '!=', 'manual')]))
    reject_fee_journal = fields.Property(
        fields.Many2One('account.journal', 'Reject Fee Journal',
            domain=[('type', '=', 'write-off')]))

    def export_json(self, skip_fields=None, already_exported=None,
            output=None, main_object=None, configuration=None):
        values = super(Configuration, self).export_json(skip_fields,
            already_exported, output, main_object, configuration)

        if 'direct_debit_journal' not in values:
            return values
        field_value = getattr(self, 'direct_debit_journal')
        values['direct_debit_journal'] = {'_func_key': getattr(
            field_value, field_value._func_key)}
        return values

    def get_payment_journal(self, line):
        return self.direct_debit_journal


class Group(ModelCurrency, export.ExportImportMixin):
    __name__ = 'account.payment.group'
    _func_key = 'reference'

    processing_payments = fields.One2ManyDomain('account.payment', 'group',
        'Processing Payments',
        domain=[('state', '=', 'processing')])
    state = fields.Function(
        fields.Selection([('', ''), ('processing', 'Processing')], 'State'),
        'get_state')
    amount = fields.Function(
        fields.Numeric('Amount', digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']),
        'get_amount')
    payment_dates = fields.Function(
        fields.Char('Payment Dates'),
        'get_payment_dates')

    @classmethod
    def __setup__(cls):
        super(Group, cls).__setup__()
        cls._buttons.update({
                'acknowledge': {
                    'invisible': Eval('state') != 'processing',
                    },
                })

    @classmethod
    def view_attributes(cls):
        return super(Group, cls).view_attributes() + [
            ('/tree', 'colors', If(
                    Eval('state') == 'processing',
                    'blue',
                    'black')),
            ]

    @classmethod
    def _export_skips(cls):
        return super(Group, cls)._export_skips() | {'payments',
            'processing_payments'}

    @classmethod
    def _export_light(cls):
        return super(Group, cls)._export_light() | {'journal', 'company'}

    @classmethod
    @ModelView.button
    def acknowledge(cls, groups):
        Payment = Pool().get('account.payment')
        payments = []
        for group in groups:
            payments.extend(group.processing_payments)
        Payment.succeed(payments)

    def get_currency(self):
        return self.journal.currency if self.journal else None

    @classmethod
    def get_state(cls, groups, name):
        pool = Pool()
        cursor = Transaction().cursor
        account_payment = pool.get('account.payment').__table__()
        result = {x.id: False for x in groups}

        cursor.execute(*account_payment.select(account_payment.group,
                where=((account_payment.state == 'processing')
                    & (account_payment.group.in_([x.id for x in groups]))),
                group_by=[account_payment.group]))

        for group_id, in cursor.fetchall():
            result[group_id] = 'processing'
        return result

    @classmethod
    def get_amount(cls, groups, name):
        pool = Pool()
        cursor = Transaction().cursor
        account_payment = pool.get('account.payment').__table__()
        result = {x.id: None for x in groups}

        cursor.execute(*account_payment.select(
                account_payment.group, Sum(account_payment.amount),
                where=account_payment.group.in_([x.id for x in groups]),
                group_by=[account_payment.group]))

        for group_id, amount in cursor.fetchall():
            result[group_id] = amount
        return result

    @classmethod
    def get_payment_dates(cls, groups, name):
        pool = Pool()
        Date = pool.get('ir.date')
        cursor = Transaction().cursor
        account_payment = pool.get('account.payment').__table__()
        result = {x.id: '' for x in groups}

        cursor.execute(*account_payment.select(
                account_payment.group, account_payment.date,
                where=account_payment.group.in_([x.id for x in groups]),
                group_by=[account_payment.group, account_payment.date]))

        for group_id, date in cursor.fetchall():
            if result[group_id]:
                result[group_id] += ', '
            result[group_id] += Date.date_as_string(date)
        return result

    def merge_payment_key(self, payment):
        return (('merged_id', payment.merged_id),
            ('party', payment.party),
            ('currency', payment.currency),
            )


class PaymentMotive(model.CoopSQL, model.CoopView):
    'Payment Motive'

    __name__ = 'account.payment.motive'
    _func_key = 'code'

    code = fields.Char('Code', required=True)
    name = fields.Char('Name', required=True)

    @classmethod
    def __setup__(cls):
        super(PaymentMotive, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('code_uniq', Unique(t, t.code), 'The code must be unique!'),
            ]

    @fields.depends('code', 'name')
    def on_change_with_code(self):
        if self.code:
            return self.code
        return coop_string.slugify(self.name)


class PaymentFailInformation(model.CoopView):
    'Payment Fail Information'
    __name__ = 'account.payment.fail_information'

    reject_reason = fields.Many2One('account.payment.journal.reject_reason',
        'Reject Reason', depends=['process_method'],
        domain=[('process_method', '=', Eval('process_method'))],
        required=True)
    payments = fields.One2Many('account.payment', None, 'Payments',
        readonly=True)
    process_method = fields.Char('Process Method')

    @fields.depends('payments')
    def on_change_with_process_method(self, name=None):
        methods = [p.journal.process_method for p in self.payments]
        methods = list(set(methods))
        if len(methods) == 1:
            return methods[0]
        else:
            return ''


class ManualPaymentFail(model.CoopWizard):
    'Fail Payment'
    __name__ = 'account.payment.manual_payment_fail'

    start_state = 'fail_information'
    fail_information = StateView('account.payment.fail_information',
        'account_payment_cog.payment_fail_information_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Fail Payments', 'fail_payments', 'tryton-ok', default=True)
            ])
    fail_payments = StateTransition()

    @classmethod
    def __setup__(cls):
        super(ManualPaymentFail, cls).__setup__()
        cls._error_messages.update({
                'not_same_payment_method': 'Selected payments must have the '
                'same payment method.',
                'payment_must_be_succeed_processing': 'Selected payments '
                'status must be succeeded or processing'
                })

    def default_fail_information(self, values):
        pool = Pool()
        Payment = pool.get('account.payment')
        active_model = Transaction().context.get('active_model')
        active_ids = Transaction().context.get('active_ids')
        if active_model == 'account.payment.merged':
            payments = Payment.browse(active_ids)
            merged_ids = [x.merged_id for x in payments]
            active_ids = [x.id for x in Payment.search(
                    [('merged_id', 'in', merged_ids)])]
        if any([x.state not in ('succeeded', 'processing')
                for x in Payment.browse(active_ids)]):
            self.raise_user_error('payment_must_be_succeed_processing')
        return {
            'payments': active_ids
            }

    def transition_fail_payments(self):
        pool = Pool()
        Payment = pool.get('account.payment')
        if not self.fail_information.process_method:
            self.raise_user_error('not_same_payment_method')
        Payment.manual_set_reject_reason(list(self.fail_information.payments),
            self.fail_information.reject_reason)
        Payment.fail(list(self.fail_information.payments))
        return 'end'


class ProcessManualFailPament(model.CoopWizard):
    'Process Manual Fail Payment'
    __name__ = 'account.payment.process_manual_fail_payment'

    start_state = 'set_fail_status'
    set_fail_status = StateTransition()

    def transition_set_fail_status(self):
        pool = Pool()
        Payment = pool.get('account.payment')
        active_ids = Transaction().context.get('active_ids')
        Payment.write(Payment.browse(active_ids),
            {'manual_fail_status': 'done'})
        return 'end'

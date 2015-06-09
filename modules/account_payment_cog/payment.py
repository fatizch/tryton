# -*- coding:utf-8 -*-
from collections import defaultdict
from itertools import groupby

from trytond import backend
from trytond.transaction import Transaction
from trytond.model import ModelView
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval

from trytond.modules.cog_utils import coop_string, export, fields, model
from trytond.modules.cog_utils import coop_date, utils

__metaclass__ = PoolMeta

__all__ = [
    'Payment',
    'Configuration',
    'Journal',
    'JournalFailureAction',
    'RejectReason',
    'Group'
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

    def get_fail_action(self, payments):
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
                return action.action
        return ('manual')

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
            'reject_reason', 'rejected_payment_fee'}

    @classmethod
    def get_rejected_payment_fee(cls, code):
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
        cls._sql_constraints += [
            ('code_unique', 'UNIQUE(code)',
                'The code must be unique'),
            ]

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


class Payment(export.ExportImportMixin):
    __name__ = 'account.payment'
    _func_key = 'id'

    manual_fail_status = fields.Selection([
        ('', ''),
        ('pending', 'Pending'),
        ('done', 'Done')
        ], 'Manual Fail Status')
    reject_description = fields.Function(
        fields.Char('Reject Description', states={
                'invisible': ~Eval('reject_description')}),
        'get_reject_description')

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
        cls._error_messages.update({
                'action_not_found': 'Action "%s" not found for payments %s',
                'payments_blocked_for_party': 'Payments blocked for party %s',
                })

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
                coop_string.translate_value(self, 'state'))
        else:
            return '%s - %s - [%s]' % (
                Date.date_as_string(self.date),
                self.currency.amount_as_string(self.amount),
                coop_string.translate_value(self, 'state'))

    def _get_transaction_key(self):
        """
            Return the key to identify payments processed in one transaction
            Overriden in account_payment_sepa_cog
        """
        return (self, self.journal)

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
            action = key[1].get_fail_action(payments_list)
            if action:
                actions['fail_%s' % action].extend(payments_list)
            else:
                cls.raise_user_error('action_not_found', (
                    payments_list[0].fail_code, ', '.join(payment.rec_name
                        for payment in payments_list)))

        for action, payments in actions.iteritems():
            getattr(cls, action)(payments)

    @classmethod
    def fail_manual(cls, payments):
        cls.write(payments, {
                'manual_fail_status': 'pending',
                })

    @classmethod
    def fail_retry(cls, payments):
        pass

    @fields.depends('line')
    def on_change_line(self):
        super(Payment, self).on_change_line()
        if self.line:
            self.date = self.line.payment_date

    @classmethod
    def is_master_object(cls):
        return True

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
        Event.notify_events(payments, 'process_payment')
        return group

    @classmethod
    def succeed(cls, payments):
        pool = Pool()
        Event = pool.get('event')
        super(Payment, cls).succeed(payments)
        Event.notify_events(payments, 'succeed_payment')


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


class Group:
    __name__ = 'account.payment.group'

    processing_payments = fields.One2ManyDomain('account.payment', 'group',
        'Processing Payments',
        domain=[('state', '=', 'processing')])
    has_processing_payment = fields.Function(fields.Boolean(
        'Has Processing Payment'), 'get_has_processing_payment')

    @classmethod
    def __setup__(cls):
        super(Group, cls).__setup__()
        cls._buttons.update({
                'acknowledge': {
                    'invisible': ~Eval('has_processing_payment'),
                    },
                })

    @classmethod
    @ModelView.button
    def acknowledge(cls, groups):
        Payment = Pool().get('account.payment')
        payments = []
        for group in groups:
            payments.extend(group.processing_payments)
        Payment.succeed(payments)

    @classmethod
    def get_has_processing_payment(cls, groups, name):
        pool = Pool()
        cursor = Transaction().cursor
        account_payment = pool.get('account.payment').__table__()
        result = {x.id: False for x in groups}

        cursor.execute(*account_payment.select(account_payment.group,
                where=(account_payment.state == 'processing'),
                group_by=[account_payment.group]))

        for group_id, in cursor.fetchall():
            result[group_id] = True
        return result

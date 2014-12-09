# -*- coding:utf-8 -*-
from trytond.transaction import Transaction
from trytond.model import ModelView
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from collections import defaultdict

from trytond.modules.cog_utils import coop_string, export, fields, model

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
        'journal', 'Failure Actions')

    def get_action(self, code):
        for action in self.failure_actions:
            if action.reject_reason.code == code:
                return action.action


class JournalFailureAction(model.ModelSQL, model.ModelView):
    'Payment Journal Failure Action'

    __name__ = 'account.payment.journal.failure_action'
    _rec_name = 'reject_reason'

    reject_reason = fields.Many2One('account.payment.journal.reject_reason',
        'Reject Reason', required=True, ondelete='RESTRICT')
    journal = fields.Many2One('account.payment.journal', 'Journal',
        required=True, ondelete='CASCADE', select=True)
    action = fields.Selection([
            ('manual', 'Manual'),
            ('retry', 'Retry'),
            ], 'Action')

    @classmethod
    def __setup__(cls):
        super(JournalFailureAction, cls).__setup__()
        cls._sql_constraints += [
            ('code_unique', 'UNIQUE(journal, reject_reason)',
                'Action must be unique for a journal and a reject reason'),
            ]


class RejectReason(model.ModelSQL, model.ModelView):
    'Payment Journal Reject Reason'
    __name__ = 'account.payment.journal.reject_reason'

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

    def get_rec_name(self, name):
        return '[%s] %s' % (self.code, self.description)

    @classmethod
    def search_rec_name(cls, name, clause):
        return ['OR',
            [(u'code',) + tuple(clause[1:])],
            [(u'description',) + tuple(clause[1:])]
            ]


class Payment:
    __name__ = 'account.payment'

    @classmethod
    def __setup__(cls):
        super(Payment, cls).__setup__()
        cls._error_messages.update({
                'action_not_found': 'Action "%s" not found for payment %s',
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

    @property
    def fail_code(self):
        pass

    @classmethod
    def fail(cls, payments):
        super(Payment, cls).fail(payments)

        actions = defaultdict(list)
        for payment in payments:
            if not payment.line:
                continue

            if len(payment.line.payments) == 1:
                action = payment.journal.get_action(payment.fail_code)

                if action:
                    actions['fail_%s' % action].append(payment)
                else:
                    cls.raise_user_error('action_not_found', (
                        payment.fail_code, payment.rec_name))

            else:
                actions['fail_manual'].append(payment)

        for action, payments in actions.iteritems():
            getattr(cls, action)(payments)

    @classmethod
    def fail_manual(cls, payments):
        pass

    @classmethod
    def fail_retry(cls, payments):
        pass

    @fields.depends('line')
    def on_change_line(self):
        super(Payment, self).on_change_line()
        if self.line:
            self.date = self.line.payment_date


class Configuration:
    __name__ = 'account.configuration'

    direct_debit_journal = fields.Property(
        fields.Many2One('account.payment.journal', 'Direct Debit Journal',
            domain=[('process_method', '!=', 'manual')]))

    def export_json(self, skip_fields=None, already_exported=None,
            output=None, main_object=None):
        values = super(Configuration, self).export_json(skip_fields,
            already_exported, output, main_object)

        field_value = getattr(self, 'direct_debit_journal')
        values['direct_debit_journal'] = {'_func_key': getattr(
            field_value, field_value._func_key)}
        return values


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

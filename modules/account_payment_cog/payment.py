# -*- coding:utf-8 -*-
from trytond.transaction import Transaction
from trytond.model import ModelSQL, ModelView
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval

from trytond.modules.cog_utils import coop_string, export, fields

__metaclass__ = PoolMeta

__all__ = [
    'Payment',
    'Configuration',
    'Journal',
    'Group'
    ]


class Payment(ModelSQL, ModelView):
    __name__ = 'account.payment'

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


class Journal(export.ExportImportMixin):
    __name__ = 'account.payment.journal'
    _func_key = 'name'

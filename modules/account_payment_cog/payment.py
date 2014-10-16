# -*- coding:utf-8 -*-
from itertools import groupby
from sql.aggregate import Count
from sql.operators import Equal

from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from trytond.model import ModelView, ModelSQL, fields

from trytond.modules.cog_utils import coop_string, batchs

__metaclass__ = PoolMeta

__all__ = [
    'Payment',
    'PaymentTreatmentBatch',
    'PaymentCreationBatch',
    'Configuration',
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
        change = super(Payment, self).on_change_line()
        if change and self.line:
            change['date'] = self.line.payment_date
        return change


class Configuration:
    __name__ = 'account.configuration'

    direct_debit_journal = fields.Property(
        fields.Many2One('account.payment.journal', 'Direct Debit Journal',
            domain=[('process_method', '!=', 'manual')]))


class PaymentTreatmentBatch(batchs.BatchRoot):
    "Payment Treatment Batch"
    __name__ = 'account.payment.treatment'

    @classmethod
    def get_batch_main_model_name(cls):
        return 'account.payment'

    @classmethod
    def get_batch_search_model(cls):
        return 'account.payment'

    @classmethod
    def get_batch_name(cls):
        return 'Payment treatment batch'

    @classmethod
    def get_batch_stepping_mode(cls):
        return 'divide'

    @classmethod
    def get_batch_step(cls):
        return 1

    @classmethod
    def get_batch_domain(cls, treatment_date):
        return [
            ('state', '=', 'approved'),
            ('date', '<=', treatment_date)]

    @classmethod
    def _group_payment_key(cls, payment):
        return (('journal', payment.journal.id), ('kind', payment.kind))

    @classmethod
    def execute(cls, objects, ids, logger, treatment_date):
        groups = []
        Payment = Pool().get('account.payment')
        payments = sorted(objects, key=cls._group_payment_key)
        for key, grouped_payments in groupby(payments,
                key=cls._group_payment_key):
            def group():
                pool = Pool()
                Group = pool.get('account.payment.group')
                group = Group(**dict(key))
                group.save()
                groups.append(group)
                return group
            grouped_payments = list(grouped_payments)
            Payment.process(list(grouped_payments), group)


class PaymentCreationBatch(batchs.BatchRoot):
    "Payment Creation Batch"
    __name__ = 'account.payment.creation'

    @classmethod
    def get_batch_main_model_name(cls):
        return 'account.move.line'

    @classmethod
    def get_batch_search_model(cls):
        return 'account.move.line'

    @classmethod
    def get_batch_name(cls):
        return 'Payment creation batch'

    @classmethod
    def get_batch_stepping_mode(cls):
        return 'divide'

    @classmethod
    def get_batch_step(cls):
        return 1

    @classmethod
    def select_ids(cls, treatment_date):
        cursor = Transaction().cursor
        pool = Pool()
        payment = pool.get('account.payment').__table__()
        move_line = pool.get('account.move.line').__table__()
        account = pool.get('account.account').__table__()

        query_table = move_line.join(account, condition=(
                (move_line.account == account.id)
                & (account.kind == 'receivable'))
                & (move_line.reconciliation == None)
                & (move_line.payment_date <= treatment_date))

        cursor.execute(*query_table.select(move_line.id,
            where=Equal(
                payment.select(Count(payment.id), where=(
                        (payment.state != 'failed')
                        & (payment.line == move_line.id))), 0),
            group_by=move_line.id))

        return cursor.fetchall()

    @classmethod
    def execute(cls, objects, ids, logger, treatment_date):
        pool = Pool()
        MoveLine = pool.get('account.move.line')
        MoveLine.create_payments(objects)

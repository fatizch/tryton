#-*- coding:utf-8 -*-
from itertools import groupby
from sql.aggregate import Count
from sql.operators import Equal

from trytond.pool import Pool
from trytond.transaction import Transaction

from trytond.modules.cog_utils import batchs

__all__ = [
    'PaymentTreatmentBatch',
    'PaymentCreationBatch']


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
        return 'account.invoice'

    @classmethod
    def get_batch_search_model(cls):
        return 'account.invoice'

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
        invoice = pool.get('account.invoice').__table__()
        contract_invoice = pool.get('contract.invoice').__table__()
        contract = pool.get('contract').__table__()
        account = pool.get('account.account').__table__()

        query_table = invoice.join(contract_invoice, condition=(
                (invoice.id == contract_invoice.invoice)
                & (invoice.state == 'posted'))
            ).join(contract, condition=(
                (contract_invoice.contract == contract.id)
                & (contract.status != 'quote')
                & (contract.direct_debit == True))
            ).join(move_line, condition=(
                (invoice.move == move_line.move)
                & (move_line.reconciliation == None)
                & (move_line.maturity_date <= treatment_date))
            ).join(account, condition=(
                (move_line.account == account.id)
                & (account.kind == 'receivable')))

        cursor.execute(*query_table.select(invoice.id, where=Equal(
            payment.select(Count(payment.id), where=(
                    (payment.state != 'failed')
                    & (payment.line == move_line.id))), 0),
            group_by=invoice.id))

        return cursor.fetchall()

    @classmethod
    def execute(cls, objects, ids, logger, treatment_date):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        Invoice.create_payments(objects)

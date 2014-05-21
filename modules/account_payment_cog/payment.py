#-*- coding:utf-8 -*-
from itertools import groupby
from sql.aggregate import Count
from sql.operators import Equal

from trytond.model import ModelView, fields, ModelSQL
from trytond.wizard import Wizard, StateView, StateAction, Button
from trytond.pool import Pool
from trytond.transaction import Transaction

from trytond.modules.cog_utils import coop_string, utils, batchs

__all__ = ['CreateReceivablePaymentStart', 'CreateReceivablePayment',
    'Payment', 'PaymentTreatmentBatch', 'PaymentCreationBatch']


class CreateReceivablePaymentStart(ModelView):
    'Create Receivable Payment'
    __name__ = 'account.payment.create.parameters'
    until = fields.Date('Until', required=True)

    @staticmethod
    def default_until():
        Date = Pool().get('ir.date')
        return Date.today()


class CreateReceivablePayment(Wizard):
    'Create Receivable Payment'
    __name__ = 'account.payment.create'
    start = StateView('account.payment.create.parameters',
        'account_payment_cog.create_receivable_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Create', 'create_', 'tryton-ok', default=True),
            ])
    create_ = StateAction('account_payment_cog.act_payment_receivable_form')

    def do_create_(self, action):
        pool = Pool()
        Line = pool.get('account.move.line')
        Payment = pool.get('account.payment')
        Date = pool.get('ir.date')

        today = Date.today()
        lines = Line.search([
                ('account.kind', '=', 'receivable'),
                ('debit', '!=', 0),
                ('reconciliation', '=', None),
                ('payment_amount', '>', 0),
                ['OR',
                    ('maturity_date', '<=', self.start.until),
                    ('maturity_date', '=', None),
                    ],
                ('party', '!=', None),
                ('move_state', '=', 'posted'),
                ('move.origin', 'ilike', 'contract,%'),
                ])
        for line in lines:
            contract = line.move.origin
            billing_data = contract.get_billing_data(
                line.maturity_date or today)
            if (not billing_data or not billing_data.payment_method
                    or billing_data.payment_method.payment_mode !=
                    'direct_debit'):
                continue
            payment = Payment()
            currency = line.second_currency or line.account.company.currency
            company = line.account.company
            payment.journal = company.get_payment_journal(currency, 'sepa')
            payment.kind = 'receivable'
            payment.party = line.party
            # TODO check if past is allowed
            payment.date = line.maturity_date or today
            payment.amount = line.payment_amount
            payment.line = line
            payment.state = 'approved'
            payment.save()
        return action, {}


class Payment(ModelSQL, ModelView):
    __name__ = 'account.payment'

    def get_icon(self, name=None):
        return 'payment'

    def get_rec_name(self, name):
        if self.date:
            return '%s - %s - [%s]' % (
                coop_string.date_as_string(self.date),
                self.currency.amount_as_string(self.amount),
                coop_string.translate_value(self, 'state'))
        else:
            return '%s - [%s]' % (
                coop_string.date_as_string(self.date),
                self.currency.amount_as_string(self.amount),
                coop_string.translate_value(self, 'state'))


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
    def get_batch_domain(cls):
        return [
            ('state', '=', 'approved'),
            ('date', '<=', utils.today())]

    @classmethod
    def _group_payment_key(cls, payment):
        return (('journal', payment.journal.id), ('kind', payment.kind))

    @classmethod
    def execute(cls, objects, ids, logger):
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
    def select_ids(cls):
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
                & (move_line.maturity_date <= utils.today()))
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
    def execute(cls, objects, ids, logger):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        Invoice.create_payments(objects)

import os
from itertools import groupby
from collections import namedtuple

import genshi
import genshi.template

from trytond.pool import PoolMeta, Pool
from trytond.model import fields
from trytond.modules.cog_utils import export

__metaclass__ = PoolMeta
__all__ = [
    'Mandate',
    'Group',
    'Payment',
    'InvoiceLine',
    ]


loader = genshi.template.TemplateLoader(
    os.path.join(os.path.dirname(__file__), 'template'),
    auto_reload=True)


def remove_comment(stream):
    for kind, data, pos in stream:
        if kind is genshi.core.COMMENT:
            continue
        yield kind, data, pos


class Mandate(export.ExportImportMixin):
    __name__ = 'account.payment.sepa.mandate'
    _func_key = 'identification'

    def get_rec_name(self, name):
        if self.identification is None or self.party is None:
            return super(Mandate, self).get_rec_name(name)
        return '%s - %s' % (self.identification, self.party.get_rec_name(None))

    @classmethod
    def _export_skips(cls):
        return (super(Mandate, cls)._export_skips() |
            set(['payments', 'party']))

    @classmethod
    def _export_light(cls):
        return (super(Mandate, cls)._export_light() |
            set(['company', 'account_number']))


class Group:
    __name__ = 'account.payment.group'

    def sepa_merge_payment_key(self, payment):
        return (('party', payment.party),
            ('sepa_mandate', payment.sepa_mandate),
            ('sepa_bank_account_number', payment.sepa_bank_account_number),
            ('sepa_merged_id', payment.sepa_merged_id),
            ('currency', payment.currency),
            )

    def process_sepa(self):
        pool = Pool()
        Payment = pool.get('account.payment')
        Sequence = pool.get('ir.sequence')
        if self.kind == 'receivable':
            keyfunc = self.sepa_merge_payment_key
            payments = sorted(self.payments, key=keyfunc)
            for key, merged_payments in groupby(payments, key=keyfunc):
                Payment.write(list(merged_payments), {
                        'sepa_merged_id':
                        Sequence.get('account.payment.merged'),
                        })
        super(Group, self).process_sepa()

    @property
    def sepa_payments(self):
        Payment = namedtuple('Payment', [
                'sepa_instruction_id',
                'sepa_end_to_end_id',
                'currency',
                'amount',
                'sepa_mandate',
                'sepa_bank_account_number',
                'party',
                'sepa_remittance_information',
                ])
        keyfunc = self.sepa_merge_payment_key
        for key, grouped_payments in super(Group, self).sepa_payments:
            if self.kind == 'receivable':
                merged_payments = []
                grouped_payments = sorted(grouped_payments, key=keyfunc)
                for mkey, payments in groupby(grouped_payments, key=keyfunc):
                    mkey = dict(mkey)
                    amount = sum(p.amount for p in payments)
                    payment = Payment(
                        sepa_instruction_id=mkey['sepa_merged_id'],
                        sepa_end_to_end_id=mkey['sepa_merged_id'],
                        currency=mkey['currency'],
                        amount=amount,
                        sepa_mandate=mkey['sepa_mandate'],
                        sepa_bank_account_number=mkey[
                            'sepa_bank_account_number'],
                        party=mkey['party'],
                        sepa_remittance_information='',  # TODO
                        )
                    merged_payments.append(payment)
                yield key, merged_payments
            else:
                yield key, grouped_payments


class Payment:
    __name__ = 'account.payment'

    sepa_merged_id = fields.Char('SEPA Merged ID')

    def get_sepa_end_to_end_id(self, name):
        value = super(Payment, self).get_sepa_end_to_end_id(name)
        return self.sepa_merged_id or value

    @classmethod
    def __setup__(cls):
        super(Payment, cls).__setup__()
        cls._error_messages.update({
                'unknown_amount_invoice_line':
                'Unknown amount invoice line : %s %s',
                })

    @classmethod
    def search_end_to_end_id(cls, name, domain):
        result = super(Payment, cls).search_end_to_end_id(name, domain)
        return [
            'OR',
            [
                ('sepa_merged_id', '=', None),
                result,
                ],
            [
                ('sepa_merged_id',) + tuple(domain[1:]),
                ]
            ]

    @property
    def fail_code(self):
        code = super(Payment, self).fail_code
        if not code:
            return self.sepa_return_reason_code
        return code

    @classmethod
    def fail(cls, payments):
        pool = Pool()
        JournalFailureAction = pool.get(
            'account.payment.journal.failure_action')
        Invoice = pool.get('account.invoice')
        Configuration = pool.get('account.configuration')
        config = Configuration(1)

        super(Payment, cls).fail(payments)

        invoices_to_create = []
        keyfunc = lambda c: c.sepa_end_to_end_id
        payments = sorted(payments, key=keyfunc)
        for k, payments_iterator in groupby(payments, keyfunc):
            payments = list(payments_iterator)
            payment = payments[0]
            # one reject invoice per different end_to_end_id only
            reject_fee = JournalFailureAction.get_rejected_payment_fee(
                payment.sepa_return_reason_code)
            if not reject_fee:
                continue
            fee_amount = reject_fee.amount
            if fee_amount == 0:
                continue
            journal = config.reject_fee_journal
            account = reject_fee.product.template.account_revenue_used
            name_for_billing = reject_fee.name
            invoices_to_create.append(payment.create_fee_invoice(
                    fee_amount, journal, account, name_for_billing))

        new_invoices = Invoice.create([i._save_values
            for i in invoices_to_create])
        Invoice.validate_invoice(new_invoices)

    def create_fee_invoice(self, fee_amount, journal, account_for_billing,
            name_for_billing):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        # create invoice
        invoice = Invoice(
            company=self.company,
            type='out_invoice',
            journal=journal,
            party=self.party,
            invoice_address=self.party.main_address,
            currency=self.currency,
            account=self.party.account_receivable,
            state='draft',
            description=name_for_billing,
            )
        # create invoice line
        invoice.lines = self.get_fee_invoice_lines(fee_amount,
            account_for_billing, name_for_billing)
        return invoice

    def get_fee_invoice_lines(self, amount, account_for_billing,
            name_for_billing):
        pool = Pool()
        InvoiceLine = pool.get('account.invoice.line')

        return [InvoiceLine(
                type='line',
                description=self.rec_name + ' - ' + name_for_billing,
                origin=self,
                quantity=1,
                unit=None,
                unit_price=self.currency.round(amount),
                taxes=0,
                invoice_type='out_invoice',
                account=account_for_billing,
                )]


class InvoiceLine:
    __name__ = 'account.invoice.line'

    @classmethod
    def _get_origin(cls):
        return super(InvoiceLine, cls)._get_origin() + [
            'account.payment']

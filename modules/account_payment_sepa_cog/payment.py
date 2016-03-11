import os
import datetime
from itertools import groupby
from collections import namedtuple
from dateutil.relativedelta import relativedelta
from collections import defaultdict

import genshi
import genshi.template

from trytond.pyson import Eval, Or, Bool
from trytond.pool import PoolMeta, Pool
from trytond.modules.cog_utils import fields, export, coop_date, utils
from .sepa_handler import CAMT054Coog

__metaclass__ = PoolMeta
__all__ = [
    'Mandate',
    'Group',
    'Payment',
    'InvoiceLine',
    'Journal',
    'Message',
    'PaymentCreationStart',
    'PaymentCreation',
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

    @classmethod
    def __setup__(cls):
        super(Mandate, cls).__setup__()
        cls.identification.select = True

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

    @property
    def sequence_type(self):
        seq_type = super(Mandate, self).sequence_type
        if seq_type != 'RCUR':
            return seq_type
        payments = [p for p in self.payments
            if p.state not in ['draft', 'approved']]
        if (not payments
                or all(not p.sepa_mandate_sequence_type for p in payments)
                or all(p.rejected for p in payments)):
            return 'FRST'
        else:
            return seq_type

    def objects_using_me_for_party(self, party=None):
        Payment = Pool().get('account.payment')
        domain = [('sepa_mandate', '=', self)]
        if party:
            domain.append(('party', '=', party))
        return Payment.search(domain)


class Group:
    __name__ = 'account.payment.group'

    main_sepa_message = fields.Function(
        fields.Many2One('account.payment.sepa.message', 'SEPA Message'),
        'get_main_sepa_message')

    @classmethod
    def __setup__(cls):
        super(Group, cls).__setup__()
        cls._order.insert(0, ('id', 'DESC'))
        cls.state.selection += [
            ('draft', 'Draft'),
            ('waiting', 'Waiting'),
            ('done', 'Done'),
            ('canceled', 'Canceled'),
            ]

    @classmethod
    def _export_skips(cls):
        return super(Group, cls)._export_skips() | {'sepa_messages'}

    def merge_payment_key(self, payment):
        return super(Group, self).merge_payment_key(payment) + (
            ('sepa_mandate', payment.sepa_mandate),
            ('sepa_bank_account_number', payment.sepa_bank_account_number),
            )

    def update_last_sepa_receivable_date(self):
        if self.kind != 'receivable':
            return
        new_date = max([payment.date for payment in self.payments] +
                [datetime.date.min])
        if (not self.journal.last_sepa_receivable_payment_creation_date or
                new_date >
                self.journal.last_sepa_receivable_payment_creation_date):
            self.journal.last_sepa_receivable_payment_creation_date = new_date
            self.journal.save()

    def process_sepa(self):
        # This methods does not call super (defined in account_payment_sepa
        # => payment.py
        #
        # The reason is that the sepa_mandate_sequence_type is set whatever the
        # existing value is, and right before the call to generate_message. So
        # the only way to properly set the sequence_type (that is, use the
        # same sequence_type for all the payments of a given merged group) is
        # to do so in this method.
        #
        # The first part of the code is more or less a copy of the original
        # code, while the second part properly set both the merged_id and the
        # sepa sequence type.
        #
        # See https://redmine.coopengo.com/issues/1443
        pool = Pool()
        Payment = pool.get('account.payment')
        Sequence = pool.get('ir.sequence')
        mandate_type = {}
        to_write = []
        for payment in [p for p in self.payments
                if p.kind == 'payable' and not p.bank_account]:
            bank_account = payment.party.get_bank_account(payment['date'])
            if bank_account:
                to_write += [[payment], {'bank_account': bank_account}]
        if to_write:
            Payment.write(*to_write)

        to_write = []
        if self.kind == 'receivable':
            mandates = Payment.get_sepa_mandates(self.payments)
            for payment, mandate in zip(self.payments, mandates):
                if not mandate:
                    self.raise_user_error('no_mandate', payment.rec_name)
                to_write += [[payment], {'sepa_mandate': mandate}]
                if mandate.id not in mandate_type:
                    mandate_type[mandate.id] = mandate.sequence_type
            Payment.write(*to_write)

        keyfunc = self.merge_payment_key
        payments = sorted(self.payments, key=keyfunc)
        to_write = []
        for key, merged_payments in groupby(payments, key=keyfunc):
            payments = list(merged_payments)
            values = {'merged_id': Sequence.get('account.payment.merged')}
            if self.kind == 'receivable':
                values['sepa_mandate_sequence_type'] = mandate_type[
                    payments[0].sepa_mandate.id]
            to_write += [payments, values]

        Payment.write(*to_write)
        self.generate_message(_save=False)
        self.update_last_sepa_receivable_date()

    def dump_sepa_messages(self, dirpath):
        output_paths = []
        sepa_messages_waiting = [x for x in self.sepa_messages
            if x.state == 'waiting']
        for sepa_msg in sepa_messages_waiting:
            filepath = os.path.join(dirpath, sepa_msg.filename)
            with open(filepath, 'w') as _file:
                _file.write(sepa_msg.message.encode('utf-8'))
            output_paths.append(filepath)
        Message = Pool().get('account.payment.sepa.message')
        Message.do(sepa_messages_waiting)
        return output_paths

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
        keyfunc = self.merge_payment_key
        for key, grouped_payments in super(Group, self).sepa_payments:
            merged_payments = []
            grouped_payments = sorted(grouped_payments, key=keyfunc)
            for mkey, payments in groupby(grouped_payments, key=keyfunc):
                mkey = dict(mkey)
                amount = sum(p.amount for p in payments)
                payment = Payment(
                    sepa_instruction_id=mkey['merged_id'],
                    sepa_end_to_end_id=mkey['merged_id'],
                    currency=mkey['currency'],
                    amount=amount,
                    sepa_mandate=mkey.get('sepa_mandate', None),
                    sepa_bank_account_number=mkey[
                        'sepa_bank_account_number'],
                    party=mkey['party'],
                    sepa_remittance_information='',  # TODO
                    )
                merged_payments.append(payment)
            yield key, merged_payments

    def get_main_sepa_message(self, name):
        for state in ['done', 'waiting']:
            for message in reversed(self.sepa_messages):
                if message.state == state:
                    return message.id
        if self.sepa_messages:
            return self.sepa_messages[-1].id

    @classmethod
    def get_state(cls, groups, name):
        result = super(Group, cls).get_state(groups, name)
        for group in groups:
            state = result.get(group.id, None)
            if state != 'processing':
                result[group.id] = (group.main_sepa_message.state
                    if group.main_sepa_message else None)
        return result


class Payment:
    __name__ = 'account.payment'

    bank_account = fields.Many2One('bank.account', 'Bank Account',
        ondelete='RESTRICT', domain=[('owners', '=', Eval('party'))],
        depends=['party'])
    sepa_bank_reject_date = fields.Date('SEPA Bank Reject Date',
        states={'invisible': Or(
                Eval('state') != 'failed',
                Eval('journal.process_method') != 'sepa')
                })
    reject_fee_amount = fields.Function(
        fields.Numeric('Reject Fee Amount',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']),
        'get_reject_fee_amount')

    @classmethod
    def __setup__(cls):
        super(Payment, cls).__setup__()
        cls._error_messages.update({
                'unknown_amount_invoice_line':
                'Unknown amount invoice line : %s %s',
                'direct_debit_payment': 'Direct Debit Payment of',
                'direct_debit_disbursement': 'Direct Debit Disbursement of',
                'missing_bank_acount': ('Missing bank account for "%(party)s" '
                    'at "%(date)s"'),
                })
        cls.sepa_mandate.states = {'invisible': Eval('kind') == 'payable'}
        cls.sepa_mandate.depends += ['kind']

    def get_sepa_end_to_end_id(self, name):
        value = super(Payment, self).get_sepa_end_to_end_id(name)
        return self.merged_id or value

    def _get_transaction_key(self):
        if self.sepa_end_to_end_id:
            return (self.sepa_end_to_end_id, self.journal)
        return super(Payment, self)._get_transaction_key()

    @property
    def sepa_bank_account_number(self):
        if self.kind == 'receivable':
            return super(Payment, self).sepa_bank_account_number
        elif not self.bank_account:
            bank_account = self.party.get_bank_account(self.date)
            if not bank_account:
                self.raise_user_error('missing_bank_acount', {
                        'party': self.party.rec_name,
                        'date': self.date,
                        })
            self.bank_account = bank_account

        for number in self.bank_account.numbers:
            if number.type == 'iban':
                return number

    @classmethod
    def search_end_to_end_id(cls, name, domain):
        result = super(Payment, cls).search_end_to_end_id(name, domain)
        return [
            'OR',
            [
                ('merged_id', '=', None),
                result,
                ],
            [
                ('merged_id',) + tuple(domain[1:]),
                ]
            ]

    @classmethod
    def search_sepa_instruction_id(cls, name, clause):
        return cls.search_end_to_end_id(name, clause)

    @classmethod
    def get_reject_fee_amount(cls, payments, name):
        pool = Pool()
        InvoiceLine = pool.get('account.invoice.line')
        payments_filter = ['account.payment,%s' % payment.id
            for payment in payments]
        lines = InvoiceLine.search([
                ('origin', 'in', payments_filter),
                ('invoice.state', '!=', 'cancel')])
        res = defaultdict(lambda: 0)
        for line in lines:
            res[line.origin.id] += line.amount
        return res

    @property
    def fail_code(self):
        code = super(Payment, self).fail_code
        if not code:
            return self.sepa_return_reason_code
        return code

    @classmethod
    def fail(cls, payments):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        ContractInvoice = pool.get('contract.invoice')
        Configuration = pool.get('account.configuration')
        MoveLine = pool.get('account.move.line')
        config = Configuration(1)

        invoices_to_create = []
        contract_invoices_to_create = []
        payment_date_to_update = []
        payments_keys = [(x._get_transaction_key(), x) for x in payments]
        payments_keys = sorted(payments_keys, key=lambda x: x[0])
        for key, payments_by_key in groupby(payments_keys, key=lambda x: x[0]):
            payments_list = [payment[1] for payment in payments_by_key]
            payment = payments_list[0]
            sepa_mandate = None
            payment_date = None
            reject_fee = cls.get_reject_fee(payments_list)
            if not reject_fee or not reject_fee.amount:
                continue
            if 'retry' in [action[0] for action in
                    key[1].get_fail_actions(payments_list)]:
                sepa_mandate = payment.sepa_mandate
                payment_date = payment.journal.get_next_possible_payment_date(
                        payment.line, payment.date.day)
            journal = config.reject_fee_journal
            account = reject_fee.product.template.account_revenue_used
            name_for_billing = reject_fee.name
            invoice = payment.create_fee_invoice(
                reject_fee.amount, journal, account, name_for_billing,
                sepa_mandate)
            contract = cls.get_contract_for_reject_invoice(payments_list)
            if contract is not None:
                contract_invoice = ContractInvoice(
                    contract=contract, invoice=invoice, non_periodic=True)
                contract_invoices_to_create.append(contract_invoice)
            invoices_to_create.append(invoice)
            payment_date_to_update.append({'payment_date': payment_date})

        Invoice.save(invoices_to_create)
        ContractInvoice.save(contract_invoices_to_create)
        Invoice.post(invoices_to_create)
        lines_to_write = []
        for i, p in zip(invoices_to_create, payment_date_to_update):
            lines_to_write += [list(i.lines_to_pay), p]
        if lines_to_write:
            MoveLine.write(*lines_to_write)

        super(Payment, cls).fail(payments)

    @classmethod
    def get_reject_fee(cls, payments):
        pool = Pool()
        JournalFailureAction = pool.get(
            'account.payment.journal.failure_action')
        # One reject invoice per different end_to_end_id only
        reject_fee = JournalFailureAction.get_rejected_payment_fee(
            payments[0].sepa_return_reason_code)
        return reject_fee

    @classmethod
    def payments_fields_to_update_after_fail(cls, reject_reason):
        fields = super(Payment, cls).payments_fields_to_update_after_fail(
            reject_reason)
        fields.update({
            'sepa_return_reason_code': reject_reason.code,
            'sepa_bank_reject_date': utils.today(),
        })
        return fields

    @classmethod
    def get_contract_for_reject_invoice(cls, payments):
        # Contract to attach invoice fee
        contract = None
        for payment in payments:
            if not payment.line.contract or \
                    payment.line.contract.status == 'void':
                # Void contracts cannot be invoiced anyway
                continue
            if not contract:
                contract = payment.line.contract
                continue
            if contract == payment.line.contract:
                continue
            return None
        return contract

    def get_description(self, lang=None):
        description = super(Payment, self).get_description(lang)
        if description or (not self.journal
                or self.journal.process_method != 'sepa'):
            return description
        if not lang:
            lang = self.journal.company.party.lang
        descriptions = []
        if self.kind == 'payable':
            descriptions.append(self.raise_user_error(
                    'direct_debit_disbursement', raise_exception=False))
        elif self.kind == 'receivable':
            descriptions.append(self.raise_user_error(
                    'direct_debit_payment', raise_exception=False))
        descriptions.append(lang.strftime(self.date, lang.code, lang.date)
            if self.date else '')
        return ' '.join(descriptions)

    def create_fee_invoice(self, fee_amount, journal, account_for_billing,
            name_for_billing, sepa_mandate):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        AccountConfiguration = pool.get('account.configuration')
        account_configuration = AccountConfiguration(1)

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
            sepa_mandate=sepa_mandate,
            payment_term=account_configuration.default_customer_payment_term,
            invoice_date=utils.today()
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


class Journal:
    __name__ = 'account.payment.journal'

    last_sepa_receivable_payment_creation_date = fields.Date(
        'Last Receivable Payment SEPA Creation',
        states={'invisible': Eval('process_method') != 'sepa'},
        depends=['process_method'])
    split_sepa_messages_by_sequence_type = fields.Boolean(
        'Split Sepa Messages By Sequence Type (FRST-RCUR)',
        states={'invisible': Eval('process_method') != 'sepa'},
        depends=['process_method'])

    def get_next_possible_payment_date(self, line, day):
        if self.process_method != 'sepa':
            return super(Journal, self).get_next_possible_payment_date(line,
                day)
        if self.last_sepa_receivable_payment_creation_date:
            sync_date = max(line['maturity_date'], utils.today(),
                self.last_sepa_receivable_payment_creation_date +
                relativedelta(days=1))
        else:
            sync_date = max(line['maturity_date'], utils.today())
        return coop_date.get_next_date_in_sync_with(sync_date, day)

    @classmethod
    def _export_light(cls):
        return super(Journal, cls)._export_light() | {
            'sepa_bank_account_number'}


class Message:
    __name__ = 'account.payment.sepa.message'

    @staticmethod
    def _get_handlers():
        pool = Pool()
        Payment = pool.get('account.payment')
        return {
            'urn:iso:std:iso:20022:tech:xsd:camt.054.001.01':
            lambda f: CAMT054Coog(f, Payment),
            'urn:iso:std:iso:20022:tech:xsd:camt.054.001.02':
            lambda f: CAMT054Coog(f, Payment),
            'urn:iso:std:iso:20022:tech:xsd:camt.054.001.03':
            lambda f: CAMT054Coog(f, Payment),
            'urn:iso:std:iso:20022:tech:xsd:camt.054.001.04':
            lambda f: CAMT054Coog(f, Payment),
            }


class PaymentCreationStart:
    __name__ = 'account.payment.payment_creation.start'

    bank_account = fields.Many2One('bank.account', 'Bank Account',
        domain=[
            ('owners', '=', Eval('party')),
            ['OR', ('end_date', '>=', Eval('payment_date')),
                ('end_date', '=', None)],
            ['OR', ('start_date', '<=', Eval('payment_date')),
                ('start_date', '=', None)],
            ],
        states={
            'invisible': (~Bool(Eval('process_method')) |
                (Eval('process_method') != 'sepa')),
            'required': (Eval('process_method') == 'sepa') & Bool(
                Eval('Party')),
            },
        depends=['party', 'process_method', 'payment_date'])


class PaymentCreation:
    __name__ = 'account.payment.creation'

    def init_payment(self, payment):
        super(PaymentCreation, self).init_payment(payment)
        if self.start.bank_account:
            payment['bank_account'] = self.start.bank_account

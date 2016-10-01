# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import os
import re
import datetime
from itertools import groupby
from collections import namedtuple
from dateutil.relativedelta import relativedelta
from collections import defaultdict
from sql.aggregate import Sum, Max
from sql import Literal, Null
from sql.conditionals import Case
from sql.operators import Not

import genshi
import genshi.template

from trytond.transaction import Transaction
from trytond.pyson import Eval, Or, Bool
from trytond.pool import PoolMeta, Pool
from trytond.modules.coog_core import fields, export, coog_date, utils
from .sepa_handler import CAMT054Coog

__metaclass__ = PoolMeta
__all__ = [
    'Mandate',
    'Group',
    'Payment',
    'InvoiceLine',
    'Journal',
    'Message',
    'MergedPayments',
    'PaymentCreationStart',
    'PaymentCreation',
    ]

PARTY_PLACEHOLDER = re.compile(r'{party_(\w*)}')

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
        cls._error_messages.update({
                'bad_place_holders': 'Bad placeholders in SEPA Sequence. '
                "The following fields do not exist on Party model:\n\t%s\n"
                "Please check the sequence's prefix and suffix."
                })

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

    @classmethod
    def get_clause_for_frst(cls, payment_table):
        return (Not(payment_table.state.in_(('draft', 'approved'))))

    @classmethod
    def get_initial_sequence_type_per_mandates(cls, mandates):
        Payment = Pool().get('account.payment')
        payment = Payment.__table__()
        mandate = cls.__table__()
        cursor = Transaction().connection.cursor()
        ignore_clause = cls.get_clause_for_frst(payment)
        rejected_clause = ((payment.state == 'failed') &
        (payment.sepa_mandate_sequence_type != Null) &
            (payment.sepa_return_reason_information == '/RTYP/RJCT'))

        # The logic here is identical to that of the sequence_type method
        # For each mandates, we count all (not draft or approved) payments,
        # all rejected (not draft or approved) payments, and all
        # (not draft or approved) payments without sepa_mandate_sequence_type.
        # If there are no payments, or all payments are rejected or
        # they have no sepa_mandate_sequence_type,
        # then the mandate is FRST. Else it is RCUR
        # Except if it is OOFF.
        sub_query = payment.join(mandate,
            condition=((mandate.id == payment.sepa_mandate) &
                (payment.sepa_mandate.in_([x.id for x in mandates])))
            ).select(payment.sepa_mandate, mandate.type,
                Sum(
                    Case((ignore_clause, 1),
                        else_=0)).as_('count_all'),
                Sum(
                    Case((rejected_clause & ignore_clause, 1),
                        else_=0)).as_('count_rejected'),
                Sum(
                    Case((((payment.sepa_mandate_sequence_type == Null) &
                        ignore_clause), 1),
                        else_=0)).as_('count_no_seq'),
                mandate.type.as_('mandate_type'),
                group_by=[payment.sepa_mandate, mandate.type]
                )

        type_ = Case(
            (sub_query.mandate_type == 'one-off', 'OOFF'),
            else_=Case((
                        (sub_query.count_all == 0) |
                        (sub_query.count_all == sub_query.count_rejected) |
                        (sub_query.count_all == sub_query.count_no_seq),
                        'FRST'),
                else_='RCUR'))

        cursor.execute(*sub_query.select(sub_query.sepa_mandate, type_))
        return dict(cursor.fetchall())

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

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        Configuration = pool.get('account.configuration')
        config = Configuration(1)
        sepa_sequence = config.sepa_mandate_sequence
        if sepa_sequence:
            cls.complete_identification_on_create(sepa_sequence, vlist)
        return super(Mandate, cls).create(vlist)

    @classmethod
    def complete_identification_on_create(cls, sepa_sequence, vlist):
        pool = Pool()
        Party = pool.get('party.party')
        Sequence = pool.get('ir.sequence')
        suffix_and_prefix = sepa_sequence.prefix or '' \
            + sepa_sequence.suffix or ''
        matches = PARTY_PLACEHOLDER.findall(suffix_and_prefix)
        if not matches:
            return
        bad_names = [name for name in matches if name not in Party._fields]
        if bad_names:
            cls.raise_user_error('bad_place_holders', ', '.join(bad_names))
        to_update = []
        for vals in vlist:
            identification = vals.get('identification', None)
            party = vals.get('party', None)
            if not identification and party:
                to_update.append((party, vals))
        for party, vals in zip(Party.browse([x[0] for x in to_update]),
                [x[1] for x in to_update]):
            identification = Sequence.get_id(sepa_sequence.id)
            for name in matches:
                identification = identification.replace(
                    '{party_%s}' % name, str(getattr(party, name)))
            vals['identification'] = identification


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
        pool = Pool()
        Payment = pool.get('account.payment')
        result = super(Group, self).merge_payment_key(payment)
        return [x for x in result if x[0] != 'party'] + [
            ('party', payment.payer),
            ('sepa_mandate', Payment.get_sepa_mandates([payment])[0]),
            ('sepa_bank_account_number', payment.sepa_bank_account_number),
            ]

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
        # See https://redmine.coopengo.com/issues/1443
        pool = Pool()
        Payment = pool.get('account.payment')
        Sequence = pool.get('ir.sequence')
        Mandate = pool.get('account.payment.sepa.mandate')
        if self.kind == 'payable':
            to_write = []
            for payment in [p for p in self.payments
                    if p.kind == 'payable' and not p.bank_account]:
                bank_account = payment.party.get_bank_account(payment['date'])
                if bank_account:
                    to_write.extend([[payment],
                            {'bank_account': bank_account}])
            if to_write:
                Payment.write(*to_write)

        to_write = []
        if self.kind == 'receivable':
            all_mandates = Payment.get_sepa_mandates(self.payments)
            mandate_type = Mandate.get_initial_sequence_type_per_mandates(
                set(all_mandates))
            keyfunc = self.merge_payment_key
            sorted_payments = sorted(self.payments, key=keyfunc)
            for key, payments in groupby(sorted_payments, key=keyfunc):
                mandate = [x[1] for x in key if x[0] == 'sepa_mandate'][0]
                if not mandate:
                    self.raise_user_error('no_mandate', payment.rec_name)
                to_write.extend([list(payments), {'sepa_mandate': mandate,
                    'merged_id': Sequence.get('account.payment.merged'),
                    'sepa_mandate_sequence_type': mandate_type[mandate.id]}])
        if to_write:
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

    def get_remittance_info(self):
        return ''

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
                    sepa_remittance_information=self.get_remittance_info(),
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
        ondelete='RESTRICT', domain=[('owners', '=', Eval('payer'))],
        depends=['payer'], states={'invisible': ~Eval('payer')})
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
    payer = fields.Function(
        fields.Many2One('party.party', 'Payer'),
        'on_change_with_payer')

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
        cls.sepa_mandate.depends += ['kind', 'payer']
        cls.sepa_mandate.domain = [x for x in cls.sepa_mandate.domain
            if x[0] != 'party']
        cls.sepa_mandate.domain.append(('party', '=', Eval('payer', -1)))

    @fields.depends('sepa_mandate')
    def on_change_with_payer(self, name=None):
        if self.sepa_mandate:
            return self.sepa_mandate.party.id

    @fields.depends('bank_account', 'sepa_mandate', 'payer')
    def on_change_party(self):
        super(Payment, self).on_change_party()
        if not self.party:
            self.bank_account = None
            self.sepa_mandate = None
            self.payer = None

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
    def succeed(cls, payments):
        super(Payment, cls).succeed(payments)
        to_update = [p for p in payments
            if (p.sepa_return_reason_code or p.sepa_bank_reject_date)]
        if to_update:
            cls.write(to_update, {
                    'sepa_return_reason_code': None,
                    'sepa_bank_reject_date': None
                    })

    @classmethod
    def get_reject_fee(cls, payments):
        pool = Pool()
        JournalFailureAction = pool.get(
            'account.payment.journal.failure_action')
        # One reject invoice per different end_to_end_id only
        reject_fee = JournalFailureAction.get_rejected_payment_fee(
            payments[0].sepa_return_reason_code, payments[0].kind)
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
            type='out',
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
                invoice_type='out',
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
            sync_date = max(line.maturity_date, utils.today(),
                self.last_sepa_receivable_payment_creation_date +
                relativedelta(days=1))
        else:
            sync_date = max(line.maturity_date, utils.today())
        return coog_date.get_next_date_in_sync_with(sync_date, day)

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


class MergedPayments:
    __name__ = 'account.payment.merged'

    @classmethod
    def table_query(cls):
        # No call to parent method : overriden to merge payments by payer
        pool = Pool()
        payment = pool.get('account.payment').__table__()
        sepa_mandate = pool.get('account.payment.sepa.mandate').__table__()
        joined_table = payment.join(sepa_mandate,
            condition=sepa_mandate.id == payment.sepa_mandate)

        return joined_table.select(
            Max(payment.id).as_('id'),
            payment.merged_id.as_('merged_id'),
            payment.journal.as_('journal'),
            sepa_mandate.party.as_('party'),
            payment.state.as_('state'),
            Literal(0).as_('create_uid'),
            Literal(0).as_('create_date'),
            Literal(0).as_('write_uid'),
            Literal(0).as_('write_date'),
            Sum(payment.amount).as_('amount'),
            where=(payment.merged_id != Null),
            group_by=[payment.merged_id, payment.journal,
                sepa_mandate.party, payment.state])


class PaymentCreationStart:
    __name__ = 'account.payment.payment_creation.start'

    bank_account = fields.Many2One('bank.account', 'Bank Account',
        domain=[
            ('id', 'in', Eval('available_bank_accounts')),
            ],
        states={
            'invisible': ((~Bool(Eval('process_method')) |
                (Eval('process_method') != 'sepa')) & Bool(
                Eval('payer'))),
            'required': (Eval('process_method') == 'sepa')
            },
        depends=['payer', 'process_method', 'payment_date',
            'available_bank_accounts'])
    available_payers = fields.Many2Many('party.party', None, None,
         'Available Payers')
    available_bank_accounts = fields.Many2Many('bank.account', None, None,
         'Available Bank Accounts')
    payer = fields.Many2One('party.party', 'Payer',
        domain=[('id', 'in', Eval('available_payers'))],
        states={
            'invisible': (~Bool(Eval('process_method')) |
                (Eval('process_method') != 'sepa')),
            'required': (Eval('process_method') == 'sepa')
            },
        depends=['available_payers', 'process_method', 'payment_date'])

    @fields.depends('payment_date', 'party', 'available_payers', 'payer',
        'available_bank_accounts', 'bank_account')
    def on_change_party(self):
        self.available_payers = self.update_available_payers()
        self.payer = self.update_payer()
        self.available_bank_accounts = self.update_available_bank_accounts()
        self.bank_account = self.update_bank_account()

    @fields.depends('payment_date', 'available_payers', 'payer',
        'available_bank_accounts', 'bank_account')
    def on_change_payer(self):
        self.available_bank_accounts = self.update_available_bank_accounts()
        self.bank_account = self.update_bank_account()

    @fields.depends('payment_date', 'party', 'available_payers', 'payer',
        'available_bank_accounts', 'bank_account')
    def on_change_payment_date(self):
        self.available_payers = self.update_available_payers()
        self.payer = self.update_payer()
        self.available_bank_accounts = self.update_available_bank_accounts()
        self.bank_account = self.update_bank_account()

    def update_available_payers(self):
        return [self.party.id] if self.party else []

    def update_available_bank_accounts(self):
        pool = Pool()
        Mandate = pool.get('account.payment.sepa.mandate')
        if not self.payer or not self.payment_date:
            return []
        possible_mandates = Mandate.search([
                ('party', '=', self.payer.id),
                ('signature_date', '<=', self.payment_date)])
        return [m.account_number.account.id for m in possible_mandates
            if (not m.account_number.account.start_date or
                m.account_number.account.start_date <= self.payment_date) and
            (not m.account_number.account.end_date or
                m.account_number.account.end_date >= self.payment_date)]

    def update_payer(self):
        if not self.available_payers:
            return
        if not self.payer:
            if len(self.available_payers) == 1:
                return self.available_payers[0].id
            else:
                return
        if self.payer not in self.available_payers:
            return
        return self.payer.id

    def update_bank_account(self):
        if not self.available_bank_accounts:
            return
        if not self.bank_account:
            if len(self.available_bank_accounts) == 1:
                self.bank_account = self.available_bank_accounts[0].id
            else:
                return
        if self.bank_account not in self.available_bank_accounts:
            return
        return self.bank_account.id


class PaymentCreation:
    __name__ = 'account.payment.creation'

    def init_payment(self, payment):
        super(PaymentCreation, self).init_payment(payment)
        if self.start.bank_account:
            payment['bank_account'] = self.start.bank_account
        if self.start.process_method == 'sepa' and self.start.payer \
                and self.start.bank_account:
            payment['sepa_mandate'] = self._get_sepa_mandate()

    def _get_sepa_mandate(self):
        pool = Pool()
        Mandate = pool.get('account.payment.sepa.mandate')
        return Mandate.search([
                ('state', '=', 'validated'),
                ('party', '=', self.start.payer.id),
                ('account_number.account', '=', self.start.bank_account.id),
                ('signature_date', '<=', self.start.payment_date)])[0]

    def default_start(self, values):
        start = super(PaymentCreation, self).default_start(values)
        start.update({'payer': start.get('party', None)})
        return start

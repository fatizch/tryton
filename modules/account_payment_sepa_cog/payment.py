# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import os
import re
import datetime
import logging
from itertools import groupby
from collections import namedtuple
from dateutil.relativedelta import relativedelta
from collections import defaultdict
from sql.aggregate import Sum, Max
from sql import Null
from sql.conditionals import Case, Coalesce
from sql.operators import Not

import genshi
import genshi.template

from trytond import backend
from trytond.config import config
from trytond.transaction import Transaction
from trytond.pyson import Eval, Or, Bool, If
from trytond.pool import PoolMeta, Pool
from trytond.modules.coog_core import fields, coog_date, utils, model
from trytond.modules.coog_core import coog_string
from .sepa_handler import CAMT054Coog

__metaclass__ = PoolMeta
__all__ = [
    'Mandate',
    'Group',
    'Payment',
    'InvoiceLine',
    'Journal',
    'Message',
    'MergedBySepaPartyMixin',
    'MergedPayments',
    'PaymentCreationStart',
    'PaymentCreation',
    ]

PARTY_PLACEHOLDER = re.compile(r'{party_(\w*)}')

loader = genshi.template.TemplateLoader(
    os.path.join(os.path.dirname(__file__), 'template'),
    auto_reload=True)

logger = logging.getLogger(__name__)


def remove_comment(stream):
    for kind, data, pos in stream:
        if kind is genshi.core.COMMENT:
            continue
        yield kind, data, pos


class Mandate(model.CoogSQL, model.CoogView):
    __name__ = 'account.payment.sepa.mandate'
    _func_key = 'identification'

    start_date = fields.Date('Start Date',
        states={
            'readonly': Eval('state').in_(['validated', 'canceled']),
            },
        domain=[If(Bool(Eval('amendment_of', False)),
                [('start_date', '!=', None)], [])],
        depends=['state', 'amendment_of'])
    amendment_of = fields.Many2One('account.payment.sepa.mandate',
        'Amendment Of',
        states={
            'readonly': Eval('state').in_(['validated', 'canceled']),
            },
        domain=[('OR', ('start_date', '=', None),
                ('start_date', '<', Eval('start_date', datetime.date.max))),
            ('identification', '=', Eval('identification')),
            ('party', '=', Eval('party'))],
        depends=['state', 'identification', 'start_date', 'party'],
        ondelete='RESTRICT',
        select=True)

    @classmethod
    def __setup__(cls):
        super(Mandate, cls).__setup__()
        cls.identification.select = True
        cls._error_messages.update({
                'bad_place_holders': 'Bad placeholders in SEPA Sequence. '
                "The following fields do not exist on Party model:\n\t%s\n"
                "Please check the sequence's prefix and suffix.",
                'origin_must_be_same': ('All SEPA mandates with identification '
                    '"%(identification)s" must have the same origin'),
                })

    @classmethod
    def __register__(cls, module_name):
        super(Mandate, cls).__register__(module_name)
        TableHandler = backend.get('TableHandler')
        TableHandler(cls, module_name).drop_constraint(
            'identification_unique')

    @classmethod
    def validate(cls, mandates):
        super(Mandate, cls).validate(mandates)
        with model.error_manager():
            cls.check_no_duplicates(mandates)

    def _get_origin(self):
        if self.amendment_of:
            return self.amendment_of._get_origin()
        return self

    @classmethod
    def check_no_duplicates(cls, mandates):
        by_identification = defaultdict(list)
        same_identifications = cls.search([('identification', 'in',
                    [x.identification for x in mandates])])
        for mandate in same_identifications:
            by_identification[mandate.identification].append(
                mandate)
        for identification, mandates in by_identification.iteritems():
            if len(set([x._get_origin() for x in mandates])) != 1:
                cls.append_functional_error('origin_must_be_same', {
                        'identification': identification})

    def get_rec_name(self, name):
        if self.identification is None or self.party is None:
            return super(Mandate, self).get_rec_name(name)
        return '%s - %s' % (self.identification, self.party.get_rec_name(None))

    @classmethod
    def search_rec_name(cls, name, clause):
        return ['OR',
            ('party.rec_name',) + tuple(clause[1:]),
            ('account_number.rec_name',) + tuple(clause[1:])]

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
        res = dict(cursor.fetchall())
        amendments_frsts = [x for x in mandates if x.amendment_of
            and res[x.id] == 'FRST']
        if amendments_frsts:
            amended_res = cls.get_initial_sequence_type_per_mandates(
                [x.amendment_of for x in amendments_frsts])
            amended_rcurs = {k for k, v in amended_res.iteritems()
                if v == 'RCUR'}
            if amended_rcurs:
                res.update({x: 'RCUR' for x in amendments_frsts
                        if x.amendment_of in amended_rcurs})
        return res

    @property
    def sequence_type(self):
        if self.type == 'one-off':
            return 'OOFF'
        payments = [p for p in self.payments if p.state not in
            ['draft', 'approved']]
        if (not payments
                or all(not p.sepa_mandate_sequence_type for p in payments)
                or all(p.rejected for p in payments)):
            return self.amendment_of.sequence_type if self.amendment_of \
                else 'FRST'
        else:
            return 'RCUR'

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
        cls.kind_string = cls.kind.translated('kind')
        cls._order.insert(0, ('id', 'DESC'))
        cls.state.selection += [
            ('draft', 'Draft'),
            ('waiting', 'Waiting'),
            ('done', 'Done'),
            ('canceled', 'Canceled'),
            ]
        cls._buttons['generate_message'].update({
                'invisible': Eval('journal_method') != 'sepa'})

    def get_sepa_template(self):
        if self.kind == 'payable':
            if self.journal.sepa_payable_flavor.endswith('-cfonb'):
                return super(Group, self).get_sepa_template()
            return loader.load('%s.xml' % self.journal.sepa_payable_flavor)
        elif self.kind == 'receivable':
            if self.journal.sepa_receivable_flavor.endswith('-cfonb'):
                return super(Group, self).get_sepa_template()
            return loader.load('%s.xml' % self.journal.sepa_receivable_flavor)

    @classmethod
    def _export_skips(cls):
        return super(Group, cls)._export_skips() | {'sepa_messages'}

    def merge_payment_key(self, payment):
        # This method is used twice when processing payments:
        # once for setting the merged_id, and once when generating the sepa
        # message. For the latter, it is used to regoup payments in combination
        # with the sepa_group_payment_key method, which uses the payment's date.
        # To prevent duplicate end_to_end_ids in the sepa_file, we need the date
        # here too.
        pool = Pool()
        Payment = pool.get('account.payment')
        result = super(Group, self).merge_payment_key(payment)
        return [x for x in result if x[0] != 'party'] + [
            ('party', payment.payer or payment.party),
            ('sepa_mandate', Payment.get_sepa_mandates([payment])[0]),
            ('sepa_bank_account_number', payment.sepa_bank_account_number),
            ('date', payment.date),
            ]

    @classmethod
    def delete(cls, instances):
        update_sepa_date = any(x.journal.process_method == 'sepa'
            and x.kind == 'receivable' for x in instances)
        Message = Pool().get('account.payment.sepa.message')
        Message.delete(sum([list(g.sepa_messages) for g in instances], []))
        super(Group, cls).delete(instances)
        if update_sepa_date:
            cls.update_last_sepa_receivable_date(overwrite=True)

    @classmethod
    def update_last_sepa_receivable_date(cls, overwrite=False):
        pool = Pool()
        payment = pool.get('account.payment').__table__()
        Journal = Pool().get('account.payment.journal')
        journals_ids = [x.id for x in Journal.search([
                    ('process_method', '=', 'sepa')])]
        if not journals_ids:
            return
        query = payment.select(Max(payment.date), payment.journal, where=(
                (payment.group != Null) & (payment.kind == 'receivable') &
                (payment.journal.in_(journals_ids))),
            group_by=payment.journal)
        cursor = Transaction().connection.cursor()
        cursor.execute(*query)
        res = cursor.fetchall()
        if not res:
            return
        for last_date, journal_id in res:
            if not last_date:
                continue
            journal = Journal(journal_id)
            if (not journal.last_sepa_receivable_payment_creation_date or
                    overwrite or
                    last_date >
                    journal.last_sepa_receivable_payment_creation_date):
                journal.last_sepa_receivable_payment_creation_date = last_date
                journal.save()

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
        self.payments_update_sepa(self.payments, self.kind)
        self.generate_message(_save=False)
        if self.kind == 'receivable':
            self.update_last_sepa_receivable_date()

    @classmethod
    def payments_update_select_ids_sepa(cls, treatment_date, payment_kind):
        pool = Pool()
        Journal = pool.get('account.payment.journal')
        payment = pool.get('account.payment').__table__()
        cursor = Transaction().connection.cursor()
        if payment_kind == 'receivable':
            key_field = payment.sepa_mandate
        else:
            key_field = payment.bank_account
        journals_ids = [x.id for x in Journal.search([
                    ('process_method', '=', 'sepa')])]
        if not journals_ids:
            return []
        select_args = (payment.id, key_field)
        select_kwargs = {'order_by': key_field}
        where_clause = (payment.date <= treatment_date) & \
            (payment.kind == payment_kind) & \
            (payment.state == 'approved') & \
            (payment.group != Null) & \
            (payment.journal.in_(journals_ids))
        if payment_kind == 'receivable':
            where_clause &= (payment.sepa_mandate != None)  # NOQA
        select_kwargs.update({'where': where_clause})
        query = payment.select(*select_args, **select_kwargs)
        cursor.execute(*query)
        results = cursor.fetchall()
        payment_ids = []
        for group_key, grouped_results in groupby(
                results, lambda x: x[1]):
            payment_ids.append([(x[0],) for x in grouped_results])
        return payment_ids

    @classmethod
    def payments_update_sepa(cls, payments, kind):
        pool = Pool()
        Sequence = pool.get('ir.sequence')
        Mandate = pool.get('account.payment.sepa.mandate')
        Payment = pool.get('account.payment')
        to_write = []
        keyfunc = cls().merge_payment_key
        sorted_payments = sorted(payments, key=keyfunc)
        if kind == 'receivable':
            all_mandates = Payment.get_sepa_mandates(payments)
            mandate_type = Mandate.get_initial_sequence_type_per_mandates(
                set(all_mandates))
        for key, payments in groupby(sorted_payments, key=keyfunc):
            values = {}
            payments = list(payments)
            if kind == 'payable':
                bank_account = next((x.bank_account for x in payments if
                        x.bank_account), None)
                if not bank_account:
                    bank_account = key['party'].get_bank_account(
                        key['date'])
                    if bank_account:
                        values['bank_account'] = bank_account
            elif kind == 'receivable':
                mandate = [x[1] for x in key if x[0] == 'sepa_mandate'][0]
                if not mandate:
                    with model.error_manager():
                        for payment in payments:
                            cls.append_functional_error('no_mandate',
                                payment.rec_name)
                values['sepa_mandate'] = mandate
                values['sepa_mandate_sequence_type'] = mandate_type[mandate.id]
            values['merged_id'] = Sequence.get('account.payment.merged')
            to_write.extend([payments, values])
        if to_write:
            Payment.write(*to_write)

    def get_remittance_info(self, payments):
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
                # create payments list in order to use it twice: to compute
                # payments amount, and to generate remittance information
                # as it is an iterable, not storing it in a variable would lead
                # to data loss
                payments_list = [p for p in payments]
                amount = sum(p.amount for p in payments_list)
                payment = Payment(
                    sepa_instruction_id=mkey['merged_id'],
                    sepa_end_to_end_id=mkey['merged_id'],
                    currency=mkey['currency'],
                    amount=amount,
                    sepa_mandate=mkey.get('sepa_mandate', None),
                    sepa_bank_account_number=mkey[
                        'sepa_bank_account_number'],
                    party=mkey['party'],
                    sepa_remittance_information=self.get_remittance_info(
                        payments_list),
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
        states={
            'invisible': ~Eval('payer'),
            'readonly': Eval('state') != 'draft'
            }, depends=['payer', 'state'])
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
        fields.Many2One('party.party', 'Account Owner'),
        'on_change_with_payer')

    @classmethod
    def __register__(cls, module_name):
        super(Payment, cls).__register__(module_name)
        cls.sepa_mandate.select = True

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
        cls.sepa_mandate.states['invisible'] = Eval('kind') == 'payable'
        cls.sepa_mandate.states['readonly'] = Eval('state') != 'draft'
        cls.sepa_mandate.depends += ['kind', 'payer', 'state']
        cls.sepa_mandate.domain = [x for x in cls.sepa_mandate.domain
            if x[0] != 'party']
        cls.sepa_mandate.domain.append(('party', '=', Eval('payer', -1)))

    @fields.depends('sepa_mandate', 'kind', 'party')
    def on_change_with_payer(self, name=None):
        if self.sepa_mandate:
            return self.sepa_mandate.party.id
        return self.init_payer()

    def init_payer(self):
        if self.kind == 'payable' and self.party:
            return self.party.id

    @fields.depends('bank_account', 'sepa_mandate', 'payer')
    def on_change_party(self):
        super(Payment, self).on_change_party()
        if not self.party:
            self.bank_account = None
            self.sepa_mandate = None
            self.payer = None

    def get_sepa_end_to_end_id(self, name):
        # No need to call super : the end_to_end_id is simply
        # the merged_id and in no case the id as defined
        # in account_payment
        return self.merged_id

    def _get_transaction_key(self):
        if self.sepa_end_to_end_id:
            return (self.sepa_end_to_end_id, self.journal)
        return super(Payment, self)._get_transaction_key()

    @property
    def sepa_bank_account_number(self):
        if self.kind == 'receivable':
            return super(Payment, self).sepa_bank_account_number
        if not self.bank_account:
            if self.payer:
                bank_account = self.payer.get_bank_account(self.date)
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
        # No need to call super : the end_to_end_id is simply
        # the merged_id and in no case the id as defined
        # in account_payment
        return [('merged_id',) + tuple(domain[1:])]

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
    def payments_fields_to_update_after_fail(cls, reject_reason):
        fields = super(Payment, cls).payments_fields_to_update_after_fail(
            reject_reason)
        fields.update({
            'sepa_return_reason_code': reject_reason.code,
            'sepa_bank_reject_date': utils.today(),
        })
        if reject_reason.process_method == 'sepa':
            fields['manual_reject_code'] = None
        return fields

    def get_description(self, lang=None):
        description = super(Payment, self).get_description(lang)
        if description or (not self.journal
                or self.journal.process_method != 'sepa'):
            return description
        if not lang:
            lang = self.journal.company.party.lang
            if not lang:
                self.journal.company.raise_user_error('missing_lang',
                    {'party': self.journal.company.rec_name})
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

    def needs_bank_account(self):
        if self.process_method == 'sepa':
            return True
        return super(Journal, self).needs_bank_account()


class Message:
    __name__ = 'account.payment.sepa.message'

    @classmethod
    def __setup__(cls):
        super(Message, cls).__setup__()
        if not config.has_option('sepa_payment', 'out_dir'):
            logger.warning('The option \'out_dir\' should be'
                ' set in the configuration file')

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

    def dump_sepa_message(self, dirpath):
        filepath = os.path.join(dirpath, self.filename)
        with open(filepath, 'w') as _f:
            _f.write(self.message.encode('utf-8'))
        return filepath

    def parse(self):
        Event = Pool().get('event')
        super(Message, self).parse()
        Event.notify_events([self], 'parse_sepa_message')

    def send(self):
        outdir = config.get('sepa_payment', 'out_dir')
        if outdir:
            outdir = os.path.normpath(outdir)
            self.dump_sepa_message(outdir)
        Event = Pool().get('event')
        super(Message, self).send()
        Event.notify_events([self], 'send_sepa_message')

    def get_filename(self, name):
        pool = Pool()
        Group = pool.get('account.payment.group')
        if not self.origin or not isinstance(self.origin, Group):
            return ''
        names = [self.origin.rec_name, self.origin.journal.name,
            self.origin.kind_string]
        payment_dates = Group.get_payment_dates_per_group(
            [self.origin], name)[self.origin.id]
        if len(payment_dates) == 1:
            names.append(payment_dates[0].strftime('%Y%m%d'))
        return coog_string.slugify('_'.join(names)) + '.xml'


class MergedBySepaPartyMixin(object):
    __metaclass__ = PoolMeta

    @classmethod
    def _table_models(cls):
        return super(MergedBySepaPartyMixin, cls)._table_models() + \
            ['account.payment.sepa.mandate']

    @classmethod
    def get_query_table(cls, tables):
        sepa_mandate = tables['account.payment.sepa.mandate']
        payment = tables['account.payment']
        base_table = super(MergedBySepaPartyMixin, cls).get_query_table(
            tables)
        return base_table.join(sepa_mandate, 'LEFT OUTER',
            condition=sepa_mandate.id == payment.sepa_mandate)

    @classmethod
    def get_select_fields(cls, tables):
        select_fields = super(MergedBySepaPartyMixin, cls).get_select_fields(
            tables)
        select_fields['party'] = Coalesce(
            tables['account.payment.sepa.mandate'].party,
            # Use 'expression' to get the actual data of the 'As' object
            select_fields['party'].expression).as_('party')
        select_fields['sepa_mandate'] = \
            tables['account.payment'].sepa_mandate.as_('sepa_mandate')
        return select_fields

    @classmethod
    def get_group_by_clause(cls, tables):
        sepa_mandate = tables['account.payment.sepa.mandate']
        payment = tables['account.payment']
        clause = super(MergedBySepaPartyMixin, cls).get_group_by_clause(
            tables)
        clause['sepa_mandate'] = payment.sepa_mandate
        clause['party'] = Coalesce(sepa_mandate.party, clause['party'])
        return clause


class MergedPayments(MergedBySepaPartyMixin):
    __name__ = 'account.payment.merged'


class PaymentCreationStart:
    __name__ = 'account.payment.payment_creation.start'

    bank_account = fields.Many2One('bank.account', 'Bank Account',
        domain=[
            ('id', 'in', Eval('available_bank_accounts')),
            ],
        states={
            'invisible': ((~Bool(Eval('process_method')) |
                (Eval('process_method') != 'sepa')) | ~Eval('payer')
                | Eval('multiple_parties')),
            'required': ((Eval('process_method') == 'sepa') &
                ~Eval('multiple_parties'))
            },
        depends=['payer', 'process_method', 'payment_date',
            'available_bank_accounts', 'kind'])
    available_payers = fields.Many2Many('party.party', None, None,
         'Available Payers')
    available_bank_accounts = fields.Many2Many('bank.account', None, None,
         'Available Bank Accounts')
    payer = fields.Many2One('party.party', 'Account Owner',
        domain=[('id', 'in', Eval('available_payers'))],
        states={
            'invisible': (~Bool(Eval('process_method')) |
                (Eval('process_method') != 'sepa') |
                Eval('multiple_parties')),
            'required': ((Eval('process_method') == 'sepa') &
                ~Eval('multiple_parties'))
            },
        depends=['available_payers', 'process_method', 'payment_date', 'kind'])

    @fields.depends('payment_date', 'party', 'available_payers', 'payer',
        'available_bank_accounts', 'bank_account', 'kind')
    def on_change_party(self):
        self.available_payers = self.update_available_payers()
        self.payer = self.update_payer()
        self.available_bank_accounts = self.update_available_bank_accounts()
        self.bank_account = self.update_bank_account()

    @fields.depends('payment_date', 'available_payers', 'payer',
        'available_bank_accounts', 'bank_account', 'kind')
    def on_change_payer(self):
        self.available_bank_accounts = self.update_available_bank_accounts()
        self.bank_account = self.update_bank_account()

    @fields.depends('payment_date', 'party', 'available_payers', 'payer',
        'available_bank_accounts', 'bank_account', 'kind')
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
        if self.kind == 'receivable':
            possible_mandates = Mandate.search([
                    ('party', '=', self.payer.id),
                    ('signature_date', '<=', self.payment_date)])
            return [m.account_number.account.id for m in possible_mandates
                if (not m.account_number.account.start_date or
                    m.account_number.account.start_date <= self.payment_date)
                and (not m.account_number.account.end_date or
                    m.account_number.account.end_date >= self.payment_date)]
        if self.kind == 'payable':
            return [a.id for a in self.payer.bank_accounts
                if (not a.start_date or a.start_date <= self.payment_date) and
                (not a.end_date or a.end_date >= self.payment_date)]
        return []

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
        mandates = Mandate.search([
                ('state', '=', 'validated'),
                ('party', '=', self.start.payer.id),
                ('account_number.account', '=', self.start.bank_account.id),
                ('signature_date', '<=', self.start.payment_date)])
        if mandates:
            return mandates[0]

    def default_start(self, values):
        start = super(PaymentCreation, self).default_start(values)
        start.update({'payer': start.get('party', None)})
        return start

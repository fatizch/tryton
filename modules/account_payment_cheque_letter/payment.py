# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from itertools import groupby

from trytond.pool import Pool
from trytond.model import fields
from trytond.pool import PoolMeta
from trytond.transaction import Transaction
from trytond.pyson import Eval, Equal, PYSONEncoder, Bool
from trytond.wizard import StateAction

__metaclass__ = PoolMeta

__all__ = [
    'Journal',
    'Group',
    'Payment',
    'MergedPayments',
    'ProcessPayment',
    'ProcessPaymentStart',
    ]


class MergedPayments:

    __name__ = 'account.payment.merged'

    formatted_string_amount = fields.Function(
        fields.Char('Formatted amount'),
        'get_formatted_string_amount')
    description = fields.Function(
        fields.Char('Description'),
        'get_description')

    def get_formatted_string_amount(self, name=None, lang=None):
        if self.amount:
            return self.currency.format_string_amount(self.amount,
                lang_code=lang)
        return ''

    @classmethod
    def get_description(cls, instances, name=None):
        ids = [x.id for x in instances]
        Payment = Pool().get('account.payment')
        payments = Payment.search([('id', 'in', ids)])
        return {x.id: x.description
            if x.journal.process_method == 'cheque_letter' else None
            for x in payments}


class Payment:
    __name__ = 'account.payment'

    is_cheque_letter = fields.Function(
        fields.Boolean('Is Cheque Letter',
            states={'invisible': True}),
        'on_change_with_is_cheque_letter')

    @classmethod
    def __setup__(cls):
        super(Payment, cls).__setup__()
        cls._error_messages.update({
                'journal_mixin_not_allowed': 'You can not print cheque letters'
                ' with other payments types',
                'cheque_number_sequence_broken': 'You must select sequencial '
                'cheque letters numbers: jump from %s to %s',
                })

    @fields.depends('journal')
    def on_change_with_is_cheque_letter(self, name=None):
        return (self.journal.process_method == 'cheque_letter' if self.journal
            else False)

    def get_icon(self, name=None):
        if self.is_cheque_letter:
            return ('cheque_letter'
                if self.state != 'failed' else 'cheque_letter_cancel')
        return super(Payment, self).get_icon(name)

    @classmethod
    def finalize_cheque_letter_processing(cls, group_ids):
        pool = Pool()
        Payment = pool.get('account.payment')
        domain = [
            ('id', 'in', group_ids),
            ('journal.process_method', '=', 'cheque_letter'),
            ('journal.validate_process', '=', True),
            ]
        groups = pool.get('account.payment.group').search(domain)
        context = {}
        to_succeed = []
        to_approve = []
        for group in groups:
            if (not group.payments or group.journal.process_method !=
                    'cheque_letter'):
                continue
            for payment in group.payments:
                cheque_number = payment.merged_id
                if cheque_number not in context:
                    context[cheque_number] = []
                if cheque_number and payment.journal.validate_process:
                    to_succeed.append(payment)
                    context[cheque_number].append(payment)
                elif not payment.merged_id:
                    # Payment has been ignored (not enough cheque provided)
                    # So rollback the payment state to 'approved' and remove it
                    # from the payment group (account.payment.group)
                    to_approve.append(payment)
                else:
                    context[cheque_number].append(payment)
        if to_approve:
            Payment.write(to_approve, {
                    'group': None,
                    'state': 'approved',
                    })
        Payment.succeed(to_succeed)
        return context


class Journal:
    __name__ = 'account.payment.journal'

    validate_process = fields.Boolean('Validate on processing', states={
            'invisible': ~Equal(Eval('process_method'),
                'cheque_letter')},
        help='Automatically validate payment on processing')

    @classmethod
    def __setup__(cls):
        super(Journal, cls).__setup__()
        cls.process_method.selection.append(('cheque_letter', 'Cheque Letter'))

    @classmethod
    def default_validate_process(cls):
        return False


class Group:
    __name__ = 'account.payment.group'

    @classmethod
    def __setup__(cls):
        super(Group, cls).__setup__()
        cls._error_messages.update({
                'cheque_process_exceed': 'The amount of processed payments '
                'exceed the given number of available cheques: '
                '%s/%s (%s ignored)',
                'no_cheque_processed': 'No cheque has been processed',
                'missing_begin_cheque_number': 'Missing begin cheque number',
                'missing_available_cheque_number':
                'Missing max available cheque number',
                })

    def process_cheque_letter(self):
        Payment = Pool().get('account.payment')
        begin_number_string = Transaction().context.get(
            'first_cheque_number', None)
        max_cheque_available = Transaction().context.get(
                'number_of_cheques', None)
        processed = 0
        ignored = 0
        to_write = []

        if begin_number_string is None or begin_number_string == '':
            self.raise_user_error('missing_begin_cheque_number')
        begin_number = int(begin_number_string)
        if max_cheque_available is None or max_cheque_available == '':
            self.raise_user_error('missing_available_cheque_number')
        max_cheque_available = int(max_cheque_available)
        for key, merged_payments in self.cheque_letter_payments:
            payments = list(merged_payments)
            if processed < max_cheque_available:
                cheque_number = str(begin_number + processed).zfill(
                    len(begin_number_string))
                to_write += [payments, {'merged_id': cheque_number}]
                processed += 1
            else:
                ignored += 1

        if ignored > 0:
            self.raise_user_warning('Too few cheques', 'cheque_process_exceed',
                (str(processed + ignored), str(max_cheque_available),
                 str(ignored)))

        if to_write:
            Payment.write(*to_write)
        else:
            self.raise_user_warning('Processing', 'no_cheque_processed')

    @classmethod
    def cheque_letter_payment_key(cls, payment):
        return (('party', payment.party), ('currency', payment.currency),
            ('description', payment.description))

    @property
    def cheque_letter_payments(self):
        payments = sorted(self.payments, key=self.cheque_letter_payment_key)
        for key, grouped_payments in groupby(payments,
                self.cheque_letter_payment_key):
            yield dict(key), grouped_payments


class ProcessPaymentStart:
    __name__ = 'account.payment.process.start'

    is_cheque_letter = fields.Boolean('Cheque letter payment',
        states={'invisible': True})
    first_cheque_number = fields.Char(
        'Cheque number to start with',
        states={'invisible': ~Eval('is_cheque_letter'),
            'required': Bool(Eval('is_cheque_letter', False))},
        depends=['is_cheque_letter'])
    number_of_cheques = fields.Integer(
        'Number of available cheque',
        states={'invisible': ~Eval('is_cheque_letter'),
            'required': Bool(Eval('is_cheque_letter', False))},
        depends=['is_cheque_letter'])

    @classmethod
    def view_attributes(cls):
        return super(ProcessPaymentStart, cls).view_attributes() + \
            [('/form/group[@id="cheque_letter_number"]', 'states',
                    {'invisible': ~Eval('is_cheque_letter')})]


class ProcessPayment:
    __name__ = 'account.payment.process'

    process_with_cheque_letter = StateAction(
        'account_payment_cog.act_payment_group_merged_form')

    def do_process_with_cheque_letter(self, action):
        Payment = Pool().get('account.payment')
        with Transaction().set_context(
                first_cheque_number=self.start.first_cheque_number,
                number_of_cheques=self.start.number_of_cheques):
            _, context = super(ProcessPayment, self).do_process(action)
            context = Payment.finalize_cheque_letter_processing(
                context['res_id'])
            domain = [('merged_id', 'in', context.keys())]
            action.update({'pyson_domain': PYSONEncoder().encode(domain)})
        return action, {}

    def transition_pre_process(self):
        if self.start.is_cheque_letter:
            return 'process_with_cheque_letter'
        else:
            return super(ProcessPayment, self).transition_pre_process()

    def default_start(self, fields):
        super(ProcessPayment, self).default_start(fields)
        Payment = Pool().get('account.payment')
        is_cheque_letter = bool(Payment.search([
                    ('journal.process_method', '=', 'cheque_letter'),
                    ('id', 'in', Transaction().context.get('active_ids')),
                    ], limit=1))
        return {
            'is_cheque_letter': is_cheque_letter,
            }

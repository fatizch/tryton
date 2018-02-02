# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.wizard import StateAction
from trytond.pyson import Eval, Bool, If, And
from trytond.wizard import StateView, Button, StateTransition
from trytond.server_context import ServerContext

from trytond.modules.coog_core import fields, model, coog_string, utils
from trytond.modules.account_payment.payment import KINDS


__all__ = [
    'Group',
    'Payment',
    'PaymentCreationStart',
    'PaymentCreation',
    'ProcessPayment',
    'ProcessPayboxUrl',
    ]


class Group:
    __metaclass__ = PoolMeta
    __name__ = 'account.payment.group'

    def generate_paybox_url(self):
        Payment = Pool().get('account.payment')
        url = super(Group, self).generate_paybox_url()
        if self.payments:
            Payment.write(list(self.payments), {'merged_id': self.number})
        return url

    @classmethod
    def acknowledge(cls, groups):
        super(Group, cls).acknowledge(groups)
        Payment = Pool().get('account.payment')
        payments = []
        for group in groups:
            payments.extend([x for x in group.get_payments()
                if x.state == 'processing'
                or (x.state == 'failed'
                    and x.journal.process_method == 'paybox')])
        if payments:
            Payment.succeed(payments)

    @classmethod
    def reject_payment_group(cls, groups, *args):
        super(Group, cls).reject_payment_group(groups, *args)
        cls._failed(groups)


class Payment:
    __metaclass__ = PoolMeta
    __name__ = 'account.payment'

    line_valid = fields.Function(fields.Boolean(
            'Line Not Valid'),
        'get_line_valid')

    @property
    def fail_code(self):
        code = super(Payment, self).fail_code
        if self.journal.process_method == 'paybox':
            return self.manual_reject_code
        return code

    @classmethod
    def __setup__(cls):
        super(Payment, cls).__setup__()
        cls._buttons.update({
                'generate_paybox': {
                    'invisible': ~And(And(Eval('state') == 'failed',
                        Eval('journal_method') != 'paybox'),
                            Bool(Eval('line_valid'))),
                    },
                })
        cls._error_messages.update({
                'multiple_parties_not_supported': 'Multiple parties is not '
                'supported',
                })

    @classmethod
    @model.CoogView.button_action(
        'account_payment_paybox_cog.act_create_paybox_from_rejected_payment')
    def generate_paybox(cls, instances):
        if len(list({x.party for x in instances})) > 1:
            cls.raise_user_error('multiple_parties_not_supported')

    def get_line_valid(self, name):
        if self.line:
            return not self.line.reconciliation and self.line.amount


class PaymentCreationStart:
    __metaclass__ = PoolMeta
    __name__ = 'account.payment.payment_creation.start'

    payment_url = fields.Char('Payment URL',
        states={'invisible': ~Eval('is_paybox'),
            'required': Bool(Eval('is_paybox'))},
        depends=['is_paybox'])

    @classmethod
    def __setup__(cls):
        super(PaymentCreationStart, cls).__setup__()
        cls.kind.domain.append(If(
                Eval('process_method') == 'paybox',
                [('kind', '=', 'receivable')],
                [('kind', 'in', [x[0] for x in KINDS])],
                ))
        cls.kind.depends.append('process_method')


class PaymentCreation(model.FunctionalErrorMixIn):
    __metaclass__ = PoolMeta
    __name__ = 'account.payment.creation'

    start_process_wizard = StateAction(
        'account_payment_cog.act_process_payments_button')

    @classmethod
    def __setup__(cls):
        super(PaymentCreation, cls).__setup__()
        cls._error_messages.update({
                'email_required': 'The email is required on the party '
                '%(party)s',
                'invalid_paybox_payment_date': 'The paybox payment must have '
                'a payment date less or equal than today (payment date: '
                '%(payment_date)s)'
                })

    @classmethod
    def get_possible_journals(cls, lines, kind=None):
        '''
        Paybox must be always available when creating a payment.
        '''
        possible_journals = set(super(
                PaymentCreation, cls).get_possible_journals(lines, kind))
        Journal = Pool().get('account.payment.journal')
        if kind != 'receivable':
            return list(possible_journals)
        return list(possible_journals | set(Journal.search(
                [('process_method', '=', 'paybox')])))

    def transition_create_payments(self):
        if (self.start.process_method == 'paybox'
                and not self.start.party.email):
            self.raise_user_error('email_required',
                {'party': self.start.party.rec_name})
        next_action = super(PaymentCreation, self).transition_create_payments()
        if self.start.process_method == 'paybox':
            with model.error_manager():
                for payment in self.start.created_payments:
                    if payment.date > utils.today():
                        self.append_functional_error(
                            'invalid_paybox_payment_date', {
                                'payment_date': coog_string.translate_value(
                                    payment, 'date'),
                                })
        return next_action

    def action_paybox(self):
        return 'start_process_wizard'

    def default_start(self, values):
        model = Transaction().context.get('active_model')
        if model == 'account.payment':
            # Here we create a paybox payment from another rejected one
            pool = Pool()
            Journal = pool.get('account.payment.journal')
            active_ids = Transaction().context.get('active_ids', [])
            payments = pool.get('account.payment').browse(active_ids)
            paybox_journal, = Journal.search(
                [('process_method', '=', 'paybox')], limit=1)
            start = {}
            start['lines_to_pay'] = [x.line.id for x in payments]
            start['total_amount'] = sum([x.amount for x in payments])
            start['description'] = ''
            start['party'] = payments[0].party.id
            start['payment_date'] = utils.today()
            start['journal'] = paybox_journal.id
            start['process_method'] = 'paybox'
            start['process_validate_payment'] = False
            start['bank_account'] = None
        else:
            start = super(PaymentCreation, self).default_start(values)
        return start

    def do_start_process_wizard(self, action):
        return action, {'ids': [x.id for x in self.start.created_payments]}


class ProcessPayboxUrl(model.CoogView):
    'Process Paybox Url'
    __name__ = 'account.payment.process.paybox_url'

    paybox_url = fields.Char('Click To Open', readonly=True)


class ProcessPayment:
    __metaclass__ = PoolMeta
    __name__ = 'account.payment.process'

    paybox_url_view = StateView('account.payment.process.paybox_url',
        'account_payment_paybox_cog.payment_process_paybox_url', [
            Button('close', 'end', 'tryton-close'),
            ])
    generate_url = StateTransition()

    def _group_payment_key(self, payment):
        return super(ProcessPayment, self)._group_payment_key(payment) + \
            (('group', payment.group
                if payment.journal.process_method == 'paybox' else None),)

    def _new_group(self, values):
        values.pop('group', None)
        return super(ProcessPayment, self)._new_group(values)

    def transition_pre_process(self):
        if self.start.is_paybox:
            return 'generate_url'
        else:
            return super(ProcessPayment, self).transition_pre_process()

    def default_paybox_url_view(self, fields):
        return {
            'paybox_url': self.paybox_url_view.paybox_url,
            }

    def transition_generate_url(self):
        _, res = self.do_process(None)
        self.paybox_url_view.paybox_url = res['paybox_url']
        return 'paybox_url_view'

    def do_process(self, action):
        # TODO: Properly postpone event notification at the end of the
        # transaction block
        with ServerContext().set_context(postpone_payment_group_event=True):
            action, res = super(ProcessPayment, self).do_process(action)
        if res['res_id']:
            pool = Pool()
            group = pool.get('account.payment.group')(res['res_id'][0])
            pool.get('event').notify_events([group], 'payment_group_created')
        return action, res

# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging
import binascii
import hmac
import hashlib
import datetime
from collections import OrderedDict

from trytond.config import config
from trytond.pool import PoolMeta, Pool
from trytond.wizard import StateAction
from trytond.transaction import Transaction
from trytond.pyson import Eval, Bool, If, Equal
from trytond.wizard import StateView, Button, StateTransition

from trytond.modules.coog_core import fields, model
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


class Payment:
    __metaclass__ = PoolMeta
    __name__ = 'account.payment'

    @property
    def fail_code(self):
        code = super(Payment, self).fail_code
        if self.journal.process_method == 'paybox':
            return self.manual_reject_code
        return code


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


class PaymentCreation:
    __metaclass__ = PoolMeta
    __name__ = 'account.payment.creation'

    start_process_wizard = StateAction(
        'account_payment_cog.act_process_payments_button')

    def action_paybox(self):
        return 'start_process_wizard'

    def default_start(self, values):
        start = super(PaymentCreation, self).default_start(values)
        start['kind'] = 'receivable'
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

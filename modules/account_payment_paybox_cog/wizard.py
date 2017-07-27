# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.wizard import StateAction

from trytond.modules.coog_core import model


__all__ = [
    'ProcessPayboxPayment',
    'CreatePayboxPayment',
    ]


class ProcessPayboxPayment(model.CoogWizard):
    'Process Paybox Payment'

    __name__ = 'paybox_payment.process'

    start = StateAction('account_payment.act_payment_group_form')

    def do_start(self, action):
        pool = Pool()
        ProcessWizard = pool.get('account.payment.process', type='wizard')
        wizard_id, _, _ = ProcessWizard.create()
        process_wizard = ProcessWizard(wizard_id)
        for key, value in process_wizard.default_start(None).items():
            setattr(process_wizard.start, key, value)
        process_wizard.is_paybox = False
        action, context_ = process_wizard.do_process(action)
        views = [x for x in action['views'] if x[1] == 'form']
        action['views'] = views
        return action, context_


class CreatePayboxPayment(model.CoogWizard):
    'Create Paybox Payment'

    __name__ = 'paybox_payment.create'

    start = StateAction(
        'account_payment_paybox_cog.act_process_paybox_payment')

    @classmethod
    def __setup__(cls):
        super(CreatePayboxPayment, cls).__setup__()
        cls._error_messages.update({
                'paybox_payment_creation':
                'Could not create paybox payments. There is at least one '
                'another validated or processing payment with the same line '
                'for the selection (%(selection)s)',
                })

    def create_payments(self, failed_payments):
        pool = Pool()
        CreatePaymentWiz = pool.get('account.payment.creation', type='wizard')
        Payment = pool.get('account.payment')
        wizard_id, _, _ = CreatePaymentWiz.create()
        create_payment = CreatePaymentWiz(wizard_id)
        for key, value in create_payment.default_start(None).items():
            setattr(create_payment.start, key, value)
        create_payment.transition_create_payments()
        _, context_ = create_payment.do_created_payments({})
        created_payments = context_['extra_context']['created_payments']
        if not created_payments:
            selection = [x for x in Payment.browse(
                    Transaction().context.get('active_ids'))]
            selection = ['%s - %s' % (x.description, x.party.rec_name)
                for x in selection]
            self.raise_user_error('paybox_payment_creation',
                {'selection': ', '.join(selection)})
        return created_payments

    def do_start(self, action):
        pool = Pool()
        Payment = pool.get('account.payment')
        payments = Payment.browse(Transaction().context.get('active_ids'))
        failed_payments = [x for x in payments if x.state == 'failed']
        created_payments = self.create_payments(failed_payments)
        payments = Payment.browse(created_payments)
        to_write = []
        for payment in payments:
            to_write.extend([[payment], {
                        'description': payment.line.description,
                        }])
        if to_write:
            Payment.write(*to_write)
        return action, {'ids': created_payments}

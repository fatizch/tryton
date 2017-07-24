from collections import defaultdict

from trytond.pool import PoolMeta, Pool
from trytond.server_context import ServerContext
from trytond.pyson import Eval

from trytond.modules.coog_core import model, fields


class PaymentSuspension(model.CoogSQL, model.CoogView):
    """
    Payment Suspension
    """
    __name__ = 'contract.payment_suspension'

    payment_line_due = fields.Many2One('account.move.line', 'Payment Due Line',
        ondelete='RESTRICT', states={'required': ~Eval('use_force')},
        depends=['use_force'], readonly=True, select=True)
    payment_line_rec_name = fields.Function(fields.Char('Payment Line'),
        'get_payment_line_rec_name')
    billing_info = fields.Many2One('contract.billing_information',
        'Billing Information', required=True, ondelete='CASCADE',
        readonly=True, select=True)
    billing_info_rec_name = fields.Function(fields.Char('Billing Information'),
        'get_billing_info_rec_name')
    use_force = fields.Boolean('Use Forced Value', readonly=True, help='If '
        'True, use the Force Active field to define whether the suspension'
        ' is active or not')
    force_active = fields.Boolean('Force Active', states={
            'invisible': ~Eval('use_force'),
            }, depends=['use_force'], readonly=True,
        help='Force the suspension status to active or inactive')
    active = fields.Function(fields.Boolean('Active'), 'get_active',
        searcher='search_active')
    color = fields.Function(fields.Char('Color'),
        'get_color')

    @classmethod
    def __setup__(cls):
        super(PaymentSuspension, cls).__setup__()
        cls._buttons.update({
                'activate': {'invisible': Eval('active')},
                'deactivate': {'invisible': ~Eval('active')}
                })

    @classmethod
    @model.CoogView.button
    def activate(cls, suspensions):
        Pool().get('contract.billing_information').suspend_payments(
            [x.billing_info for x in suspensions])

    @classmethod
    @model.CoogView.button
    def deactivate(cls, suspensions):
        Pool().get('contract.billing_information').unsuspend_payments(
            [x.billing_info for x in suspensions])

    @classmethod
    def get_payment_line_rec_name(cls, billings, name):
        return {x.id: x.payment_line_due.rec_name if x.payment_line_due else ''
            for x in billings}

    def get_billing_info_rec_name(self, name):
        billing_mode = self.billing_info.billing_mode
        payer = self.billing_info.payer
        return '%s - %s' % (billing_mode.rec_name if billing_mode else '',
            payer.rec_name if payer else '')

    @classmethod
    def search_active(cls, name, clause):
        reverse = {
            '=': '!=',
            '!=': '=',
            }
        if clause[1] not in ['=', '!=']:
            return []
        return ['OR',
            ['AND',
                [('use_force', '=', True)],
                [('force_active', clause[1] if clause[2] else
                        reverse[clause[1]], clause[2] if clause[2] else False)]
                ],
            ['AND',
                [('use_force', '=', False)],
                [('payment_line_due.reconciliation', clause[1] if clause[2]
                    else reverse[clause[1]], None)]]]

    @classmethod
    def view_attributes(cls):
        return super(PaymentSuspension, cls).view_attributes() + [(
                '/tree',
                'colors',
                Eval('color', 'black'))]

    @staticmethod
    def default_use_force():
        return False

    def get_color(self, name=None):
        if self.active:
            return 'red'
        return 'green'

    @staticmethod
    def default_force_active():
        return False

    def get_active(self, name=None):
        if self.use_force:
            return self.force_active
        return not self.payment_line_due.is_reconciled


class JournalFailureAction:
    __name__ = 'account.payment.journal.failure_action'
    __metaclass__ = PoolMeta

    @classmethod
    def __setup__(cls):
        super(JournalFailureAction, cls).__setup__()
        cls.action.selection += [
            ('suspend', 'Suspend Payments (Automatic un-suspend)'),
            ('suspend_manual', 'Suspend Payments (Manual un-suspend)'),
            ]
        cls._fail_actions_order += ['suspend', 'suspend_manual']


class Payment:
    __name__ = 'account.payment'
    __metaclass__ = PoolMeta

    @classmethod
    def fail_suspend_manual(cls, *args):
        with ServerContext().set_context(use_force=True):
            cls.fail_suspend(*args)

    @classmethod
    def fail_suspend(cls, *args):
        payments_billing = defaultdict(list)
        for payments, _ in args:
            for payment in payments:
                payments_billing[payment.line.contract.billing_information.id
                    ].append(payment)
        Pool().get('contract.billing_information').suspend_payments([],
            payments_billing)

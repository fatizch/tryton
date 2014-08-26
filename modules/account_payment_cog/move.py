from trytond.pool import PoolMeta, Pool
from trytond.model import fields
from trytond.pyson import Eval
from trytond.wizard import StateView, Button, StateTransition
from trytond.transaction import Transaction

from trytond.modules.cog_utils import model

__metaclass__ = PoolMeta

__all__ = [
    'MoveLine',
    'PaymentDateSelection',
    'PaymentDateModification',
    ]


class MoveLine:
    __name__ = 'account.move.line'

    payment_date = fields.Date('Payment Date',
        states={'invisible': (Eval('account_kind') != 'receivable') &
            (Eval('account_kind') != 'payable')},
        depends=['account_kind'])

    @classmethod
    def __setup__(cls):
        super(MoveLine, cls).__setup__()
        cls._check_modify_exclude.append('payment_date')

    def init_payment(self, journal):
        if self.debit > 0:
            kind = 'receivable'
            payment_amount = self.debit
        elif self.credit > 0:
            kind = 'payable'
            payment_amount = self.credit
        else:
            return None
        return {
            'company': self.account.company.id,
            'kind': kind,
            'journal': journal.id,
            'party': self.party.id,
            'amount': payment_amount,
            'line': self.id,
            'date': self.payment_date,
            'state': 'approved',
            }

    @classmethod
    def create_payments(cls, lines):
        pool = Pool()
        Payment = pool.get('account.payment')
        AccountConfiguration = pool.get('account.configuration')

        payments = []
        account_configuration = AccountConfiguration(1)
        journal = account_configuration.direct_debit_journal
        if journal is None:
            return None

        for line in lines:
            payment = line.init_payment(journal)
            if not payment:
                continue
            payments.append(payment)

        Payment.create(payments)


class PaymentDateSelection(model.CoopView):
    'Bank transfer Planned Date Selection'

    __name__ = 'account.payment.payment_date_selection'

    new_date = fields.Date('New Payment Date')
    move_line = fields.Many2One('account.move.line', 'Move Line')


class PaymentDateModification(model.CoopWizard):
    'Bank transfer Planned Date Modification'
    __name__ = 'account.payment.payment_date_modification'

    start_state = 'payment_date_selection'
    payment_date_selection = StateView(
        'account.payment.payment_date_selection',
        'account_payment_cog.'
        'payment_date_modification_view_form',
        [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Next', 'finalize', 'tryton-go-next', default=True),
        ])
    finalize = StateTransition()

    def default_payment_date_selection(self, values):
        pool = Pool()
        MoveLine = pool.get('account.move.line')
        cur_model = Transaction().context.get('active_model')
        if cur_model != 'account.move.line':
            raise TypeError
        move_line = MoveLine(Transaction().context.get('active_id'))
        return {
            'new_date': move_line.payment_date,
            'move_line': move_line.id,
            }

    def transition_finalize(self):
        move_line = self.payment_date_selection.move_line
        if (self.payment_date_selection.new_date and
                (self.payment_date_selection.new_date !=
                    move_line.payment_date)):
            move_line.payment_date = self.payment_date_selection.new_date
            move_line.save()
        return 'end'

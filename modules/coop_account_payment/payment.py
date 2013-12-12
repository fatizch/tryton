from trytond.model import ModelView, fields
from trytond.wizard import Wizard, StateView, StateAction, Button
from trytond.pool import Pool


__all__ = ['CreateReceivablePaymentStart', 'CreateReceivablePayment']


class CreateReceivablePaymentStart(ModelView):
    'Create Receivable Payment'
    __name__ = 'account.payment.create.parameters'
    until = fields.Date('Until', required=True)

    @staticmethod
    def default_until():
        Date = Pool().get('ir.date')
        return Date.today()


class CreateReceivablePayment(Wizard):
    'Create Receivable Payment'
    __name__ = 'account.payment.create'
    start = StateView('account.payment.create.parameters',
        'coop_account_payment.create_receivable_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Create', 'create_', 'tryton-ok', default=True),
            ])
    create_ = StateAction('coop_account_payment.act_payment_receivable_form')

    def do_create_(self, action):
        pool = Pool()
        Line = pool.get('account.move.line')
        Payment = pool.get('account.payment')
        Date = pool.get('ir.date')

        today = Date.today()
        lines = Line.search([
                ('account.kind', '=', 'receivable'),
                ('debit', '!=', 0),
                ('reconciliation', '=', None),
                ('payment_amount', '>', 0),
                ['OR',
                    ('maturity_date', '<=', self.start.until),
                    ('maturity_date', '=', None),
                    ],
                ('party', '!=', None),
                ('move_state', '=', 'posted'),
                ('move.origin', 'ilike', 'contract,%'),
                ])
        for line in lines:
            contract = line.move.origin
            billing_manager = contract.get_billing_manager(
                line.maturity_date or today)
            if (not billing_manager or not billing_manager.payment_method
                    or billing_manager.payment_method.payment_mode !=
                    'direct_debit'):
                continue
            payment = Payment()
            currency = line.second_currency or line.account.company.currency
            company = line.account.company
            payment.journal = company.get_payment_journal(currency, 'sepa')
            payment.kind = 'receivable'
            payment.party = line.party
            # TODO check if past is allowed
            payment.date = line.maturity_date or today
            payment.amount = line.payment_amount
            payment.line = line
            payment.state = 'approved'
            payment.save()
        return action, {}

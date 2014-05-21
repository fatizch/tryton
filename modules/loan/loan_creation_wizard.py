from trytond.pool import Pool
from trytond.wizard import StateTransition, StateView, Button
from trytond.transaction import Transaction

from trytond.modules.cog_utils import coop_date, model


__all__ = [
    'LoanCreate',
    ]


class LoanCreate(model.CoopWizard):
    'Loan Create'

    __name__ = 'loan.create'

    start_state = 'loan'
    loan = StateView('loan', 'loan.loan_simple_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Next', 'update_loan', 'tryton-go-next', default=True),
            ])
    update_loan = StateTransition()
    return_to_loan = StateTransition()
    loan_step_increments = StateView('loan',
        'loan.loan_only_increments_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Previous', 'return_to_loan', 'tryton-go-previous'),
            Button('Next', 'create_payments', 'tryton-go-next', default=True),
            ])
    create_payments = StateTransition()
    return_to_increments = StateTransition()
    loan_step_payments = StateView('loan', 'loan.loan_only_payments_view_form',
        [Button('Cancel', 'end', 'tryton-cancel'),
            Button('Previous', 'return_to_increments', 'tryton-go-previous'),
            Button('End', 'save_loan', 'tryton-go-next', default=True),
            ])
    save_loan = StateTransition()

    def default_loan(self, values):
        if self.loan._default_values:
            return self.loan._default_values
        Contract = Pool().get('contract')
        contract = Contract(Transaction().context.get('active_id'))
        party = Transaction().context.get('party', None)
        if party is None:
            party = contract.subscriber.id
        return {
            'contract': contract.id,
            'order': len(contract.loans) + 1,
            'currency': contract.currency.id,
            'currency_symbol': contract.currency.symbol,
            'funds_release_date': contract.start_date,
            'first_payment_date': coop_date.add_duration(
                contract.start_date, 'month'),
            'parties': [party] if party else [],
            }

    def default_loan_step_increments(self, values):
        return self.loan_step_increments._default_values

    def transition_update_loan(self):
        self.loan.calculate_increments()
        self.loan_step_increments = self.loan
        if self.loan.kind == 'graduated':
            return 'loan_step_increments'
        else:
            return 'create_payments'

    def transition_return_to_loan(self):
        self.loan = self.loan_step_increments
        return 'loan'

    def default_loan_step_payments(self, values):
        return self.loan_step_payments._default_values

    def transition_create_payments(self):
        self.loan_step_increments.check_increments()
        self.loan_step_increments.calculate_amortization_table()
        self.loan_step_payments = self.loan_step_increments
        return 'loan_step_payments'

    def transition_save_loan(self):
        LoanStepPayments = self.loan_step_payments.__class__
        with Transaction().set_user(0):
            LoanStepPayments.create([self.loan_step_payments._save_values])
        return 'end'

    def transition_return_to_increments(self):
        if self.loan_step_payments.kind == 'graduated':
            return 'loan_step_increments'
        else:
            return 'return_to_loan'

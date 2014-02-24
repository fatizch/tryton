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
    loan_step_increments = StateView('loan',
        'loan.loan_only_increments_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Previous', 'loan', 'tryton-go-previous'),
            Button('Next', 'create_payments', 'tryton-go-next', default=True),
            ])
    create_payments = StateTransition()
    loan_step_payments = StateView('loan', 'loan.loan_only_payments_view_form',
        [Button('Cancel', 'end', 'tryton-cancel'),
            Button('Previous', 'loan_step_increments', 'tryton-go-previous'),
            Button('End', 'save_loan', 'tryton-go-next', default=True),
            ])
    save_loan = StateTransition()

    def default_loan(self, values):
        if self.loan._default_values:
            return self.loan._default_values
        Contract = Pool().get('contract')
        contract = Contract(Transaction().context.get('active_id'))
        return {
            'contracts': [contract.id],
            'currency': contract.currency.id,
            'currency_symbol': contract.currency.symbol,
            'funds_release_date': contract.start_date,
            'first_payment_date': coop_date.add_duration(
                contract.start_date, 'month')
            }

    def default_loan_step_increments(self, values):
        return self.loan_step_increments._default_values

    def transition_update_loan(self):
        self.loan.calculate_increments()
        self.loan_step_increments = self.loan
        return 'loan_step_increments'

    def default_loan_step_payments(self, values):
        return self.loan_step_payments._default_values

    def transition_create_payments(self):
        self.loan_step_increments.calculate_amortization_table()
        self.loan_step_payments = self.loan_step_increments
        return 'loan_step_payments'

    def transition_save_loan(self):
        self.loan_step_payments.save()
        return 'end'

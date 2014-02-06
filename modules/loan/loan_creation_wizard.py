from trytond.pool import Pool
from trytond.wizard import StateTransition, StateView, Button
from trytond.transaction import Transaction
from trytond.pyson import Eval

from trytond.modules.cog_utils import coop_date, fields, model, utils
from trytond.modules.currency_cog import ModelCurrency

from .loan import LOAN_KIND, DEFFERALS

__all__ = [
    'LoanCreateParameters',
    'LoanCreateIncrement',
    'LoanCreateAmortizationTable',
    'LoanCreate',
    ]


class LoanCreateParameters(model.CoopView, ModelCurrency):
    'Loan Create Parameters'

    __name__ = 'loan.create.parameters'

    contract = fields.Many2One('contract', 'Contract',
        states={'invisible': True})
    loan = fields.Many2One('loan', 'Loan')
    kind = fields.Selection(LOAN_KIND, 'Kind', required=True)
    number_of_payments = fields.Integer('Number of Payments', required=True)
    payment_frequency = fields.Selection(coop_date.DAILY_DURATION,
        'Payment Frequency', required=True, sort=False)
    amount = fields.Numeric('Amount', required=True)
    funds_release_date = fields.Date('Funds Release Date', required=True)
    first_payment_date = fields.Date('First Payment Date', required=True,
        on_change_with=['funds_release_date', 'first_payment_date',
            'payment_frequency'])
    rate = fields.Numeric('Annual Rate', digits=(16, 4), states={
        'required': Eval('kind') != 'graduated',
        'invisible': Eval('kind') == 'graduated',
        })
    lender = fields.Many2One('bank', 'Lender')
    defferal = fields.Selection(DEFFERALS, 'Differal', sort=False)
    defferal_duration = fields.Integer('Differal Duration')
    loan_shares = fields.One2Many('loan.share', None,
        'Loan Shares')

    def on_change_with_first_payment_date(self):
        if self.funds_release_date and self.payment_frequency:
            return coop_date.add_duration(self.funds_release_date, 1,
                self.payment_frequency)


class LoanCreateIncrement(model.CoopView):
    'Loan Create Increments'

    __name__ = 'loan.create.increments'

    increments = fields.One2Many('loan.increment', None, 'Increments')


class LoanCreateAmortizationTable(model.CoopView):
    'Amortization Table'

    __name__ = 'loan.create.amortization_table'

    payments = fields.One2Many('loan.payment', None, 'Payments')


class LoanCreate(model.CoopWizard):
    'Loan Create'

    __name__ = 'loan.create'

    start_state = 'loan_parameters'
    loan_parameters = StateView('loan.create.parameters',
        'loan.loan_creation_parameters_view_form', [
            Button('Cancel', 'cancel_loan', 'tryton-cancel'),
            Button('Next', 'create_loan', 'tryton-go-next', default=True),
            ])
    create_loan = StateTransition()
    increments = StateView('loan.create.increments',
        'loan.loan_creation_increments_view_form', [
            Button('Cancel', 'cancel_loan', 'tryton-cancel'),
            Button('Previous', 'loan_parameters', 'tryton-go-previous'),
            Button('Next', 'create_payments', 'tryton-go-next', default=True),
            ])
    create_payments = StateTransition()
    amortization_table = StateView('loan.create.amortization_table',
        'loan.loan_creation_table_view_form', [
            Button('Cancel', 'cancel_loan', 'tryton-cancel'),
            Button('Previous', 'increments', 'tryton-go-previous'),
            Button('End', 'validate_loan', 'tryton-go-next', default=True),
            ])
    validate_loan = StateTransition()
    cancel_loan = StateTransition()

    def default_loan_parameters(self, values):
        Contract = Pool().get('contract')
        contract = Contract(Transaction().context.get('active_id'))
        return {
            'contract': contract.id,
            'currency': contract.currency.id,
            'currency_symbol': contract.currency.symbol,
            'kind': 'fixed_rate',
            'payment_frequency': 'month',
            'funds_release_date': contract.start_date,
            'first_payment_date': coop_date.add_duration(contract.start_date,
                1, 'month'),
            'loan_shares': [{
                    'start_date': contract.start_date,
                    'share': 1,
                    'person': x.party.id,
                    } for x in contract.covered_elements]
            }

    def default_increments(self, values):
        return {'increments':
            [x.id for x in self.loan_parameters.loan.increments]}

    def transition_create_loan(self):
        Loan = Pool().get('loan')
        loan = Loan()
        self.loan_parameters.loan = loan
        loan.contract = self.loan_parameters.contract
        loan.kind = self.loan_parameters.kind
        loan.payment_frequency = self.loan_parameters.payment_frequency
        loan.number_of_payments = self.loan_parameters.number_of_payments
        loan.amount = self.loan_parameters.amount
        loan.funds_release_date = self.loan_parameters.funds_release_date
        loan.rate = self.loan_parameters.rate
        loan.lender = self.loan_parameters.lender
        loan.first_payment_date = self.loan_parameters.first_payment_date
        loan.currency = loan.contract.currency
        loan.payment_amount = loan.on_change_with_payment_amount()
        loan.loan_shares = self.loan_parameters.loan_shares
        if (self.loan_parameters.defferal
                and self.loan_parameters.defferal_duration):
            loan.calculate_increments(defferal=self.loan_parameters.defferal,
                defferal_duration=self.loan_parameters.defferal_duration)
        elif loan.kind == 'intermediate':
            loan.calculate_increments(defferal='partially',
                defferal_duration=loan.number_of_payments - 1)
        elif loan.kind == 'graduated':
            loan.calculate_increments()
        loan.save()
        if loan.kind != 'graduated' and not loan.increments:
            return 'create_payments'
        return 'increments'

    def default_amortization_table(self, values):
        return {'payments': [x.id for x in self.loan_parameters.loan.payments]}

    def transition_create_payments(self):
        if hasattr(self.increments, 'increments'):
            for increment in self.increments.increments:
                increment.save()
        self.loan_parameters.loan.calculate_amortization_table(
            [self.loan_parameters.loan])
        return 'amortization_table'

    def transition_validate_loan(self):
        contract = self.loan_parameters.contract
        if not contract.loans:
            contract.loans = []
        contract.loans = list(contract.loans)
        contract.loans.append(self.loan_parameters.loan)
        contract.save()
        return 'end'

    def transition_cancel_loan(self):
        Loan = Pool().get('loan')
        if (not utils.is_none(self.loan_parameters, 'loan')
                and self.loan_parameters.loan.id > 0):
            Loan.delete([self.loan_parameters.loan])
        return 'end'

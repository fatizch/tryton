from trytond.pool import Pool
from trytond.pyson import Eval
from trytond.wizard import StateTransition, StateView, Button
from trytond.transaction import Transaction

from trytond.modules.cog_utils import coop_date, model, fields


__all__ = [
    'LoanCreate',
    'LoanSharePropagate',
    'LoanSharePropagateParameters',
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


class LoanSharePropagate(model.CoopWizard):
    'Loan Share Propagate'

    __name__ = 'loan.loan_share_propagate'

    start_state = 'parameters'
    parameters = StateView('loan.loan_share_propagate.parameters',
        'loan.loan_share_propagate_parameters_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Propagate', 'propagate', 'tryton-go-next', default=True),
            ])
    propagate = StateTransition()

    def default_parameters(self, values):
        pool = Pool()
        Contract = pool.get('contract')
        CoveredElement = pool.get('contract.covered_element')
        LoanShare = pool.get('loan.share')
        active_model = Transaction().context.get('active_model')
        id = Transaction().context.get('active_id')
        covered_element = None
        share = 1
        loan = None
        if active_model == 'contract':
            contract = Contract(id)
        elif active_model == 'contract.covered_element':
            covered_element = CoveredElement(id)
            contract = covered_element.contract
        elif active_model == 'loan.share':
            loan_share = LoanShare(id)
            covered_element = loan_share.option.covered_element
            contract = covered_element.contract
            share = loan_share.share
            loan = loan_share.loan
        return {
            'contract': contract.id,
            'possible_loans': [x.id for x in contract.loans],
            'loans': [loan.id] if loan else [],
            'possible_covered_elements': [x.id for x in
                contract.covered_elements],
            'covered_elements': [covered_element.id]
                if covered_element else [],
            'possible_options': [option.coverage.id
                for covered_element in contract.covered_elements
                for option in covered_element.options],
            'share': share,
            }

    def transition_propagate(self):
        to_create = []
        for covered_element in self.parameters.covered_elements:
            for option in [x for x in covered_element.options
                    if x.coverage in self.parameters.options]:
                found = set([])
                for loan_share in [x for x in option.loan_shares
                        if x.loan in self.parameters.loans]:
                    loan_share.share = self.parameters.share
                    loan_share.save()
                    found.add(loan_share.loan)
                for elem in set(self.parameters.loans) - found:
                    to_create.append({
                            'loan': elem.id,
                            'share': self.parameters.share,
                            'option': option.id,
                            'start_date': option.start_date,
                            'end_date': option.end_date or elem.end_date,
                            })
        Pool().get('loan.share').create(to_create)
        return 'end'


class LoanSharePropagateParameters(model.CoopView):
    'Parameters'

    __name__ = 'loan.loan_share_propagate.parameters'

    share = fields.Numeric('Share', digits=(16, 4))
    contract = fields.Many2One('contract', 'Contract',
        states={'invisible': True})
    loans = fields.Many2Many('loan', None, None, 'Loans',
        domain=[('id', 'in', Eval('possible_loans'))],
            depends=['possible_loans'], required=True)
    possible_loans = fields.Many2Many('loan', None, None, 'Possible Loans')
    covered_elements = fields.Many2Many('contract.covered_element', None, None,
        'Covered Elements',
        domain=[('id', 'in', Eval('possible_covered_elements'))],
        depends=['possible_covered_elements'], required=True)
    possible_covered_elements = fields.Many2Many('contract.covered_element',
        None, None, 'Possible Covered Elements')
    options = fields.Many2Many('offered.option.description', None, None,
        'Options', domain=[('id', 'in', Eval('possible_options'))],
        depends=['possible_options'], required=True)
    possible_options = fields.Many2Many('offered.option.description', None,
        None, 'Possible Options')

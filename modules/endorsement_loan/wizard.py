from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.wizard import StateView, Button, StateTransition
from trytond.pyson import Eval

from trytond.modules.cog_utils import fields, model
from trytond.modules.endorsement import EndorsementWizardStepBasicObjectMixin
from trytond.modules.endorsement import EndorsementWizardPreviewMixin

PAYMENT_FIELDS = ['kind', 'number', 'start_date', 'begin_balance',
    'amount', 'principal', 'interest', 'outstanding_balance']

__metaclass__ = PoolMeta
__all__ = [
    'LoanChangeBasicData',
    'LoanDisplayUpdatedPayments',
    'LoanSelectContracts',
    'SelectEndorsement',
    'PreviewLoanEndorsement',
    'StartEndorsement',
    ]


class LoanChangeBasicData(EndorsementWizardStepBasicObjectMixin,
        model.CoopView):
    'Change Basic Loan Data'

    __name__ = 'endorsement.loan.change_basic_data'
    _target_model = 'loan'

    loan = fields.Many2One('loan', 'Loan')

    def update_endorsement(self, endorsement, wizard):
        self._update_endorsement(endorsement, 'loan_fields')


class LoanDisplayUpdatedPayments(model.CoopView):
    'Display Updated Payments'

    __name__ = 'endorsement.loan.display_updated_payments'

    current_payments = fields.One2Many('loan.payment', None,
        'Current Payments', readonly=True)
    loan = fields.Many2One('loan', 'Loan', readonly=True)
    new_payments = fields.One2Many('loan.payment', None, 'New Payments',
        readonly=True)


class LoanSelectContracts(model.CoopView):
    'Select contracts related to the loan for update'

    __name__ = 'endorsement.loan.select_contracts'

    possible_contracts = fields.Many2Many('contract', None, None,
        'Possible Contracts', readonly=True)
    selected_contracts = fields.Many2Many('contract', None, None,
        'Contracts to update', depends=['possible_contracts'],
        domain=[('id', 'in', Eval('possible_contracts'))])


class SelectEndorsement:
    __name__ = 'endorsement.start.select_endorsement'

    loan = fields.Many2One('loan', 'Loan')

    @fields.depends('loan')
    def on_change_loan(self):
        return {'effective_date':
            self.loan.funds_release_date if self.loan else None}


class PreviewLoanEndorsement(EndorsementWizardPreviewMixin, model.CoopView):
    'Preview Loan Endorsement'

    __name__ = 'endorsement.start.preview_loan'

    loan = fields.Many2One('loan', 'Loan', readonly=True)
    currency_digits = fields.Integer('Currency Digits')
    currency_symbol = fields.Char('Currency Symbol')
    new_amount = fields.Numeric('New Amount', digits=(16,
            Eval('currency_digits', 2)), depends=['currency_digits'])
    new_payments = fields.One2Many('loan.payment', None, 'New Payments',
        readonly=True)
    old_amount = fields.Numeric('Current Amount', digits=(16,
            Eval('currency_digits', 2)), depends=['currency_digits'])
    old_payments = fields.One2Many('loan.payment', None,
        'Current Payments', readonly=True)

    @classmethod
    def extract_endorsement_preview(cls, instance):
        return {
            'id': instance.id,
            'amount': instance.amount,
            'payments': [dict([(x, getattr(payment, x, None))
                        for x in PAYMENT_FIELDS])
                for payment in instance.payments],
            }

    @classmethod
    def init_from_preview_values(cls, preview_values):
        result = {}
        loan_id = None
        for kind in ('old', 'new'):
            # Assume only one loan
            values = preview_values[kind].values()[0]
            loan_id = loan_id or values['id']
            for field_name in ('amount', 'payments'):
                result['%s_%s' % (kind, field_name)] = values.get(field_name,
                    None)
        if not loan_id:
            return result
        result['loan'] = loan_id
        loan = Pool().get('loan')(loan_id)
        result['currency_digits'] = loan.currency_digits
        result['currency_symbol'] = loan.currency_symbol
        return result


class StartEndorsement:
    __name__ = 'endorsement.start'

    change_basic_loan_data = StateView('endorsement.loan.change_basic_data',
        'endorsement_loan.change_basic_loan_data_view_form',
        [Button('Previous', 'change_basic_loan_data_previous',
                'tryton-go-previous'),
            Button('Suspend', 'suspend', 'tryton-save'),
            Button('Next', 'calculate_updated_payments', 'tryton-go-next',
                default=True)])
    change_basic_loan_data_previous = StateTransition()
    calculate_updated_payments = StateTransition()
    display_updated_payments = StateView(
        'endorsement.loan.display_updated_payments',
        'endorsement_loan.display_updated_payments_view_form', [
            Button('Previous', 'change_basic_loan_data', 'tryton-go-previous'),
            Button('Suspend', 'suspend', 'tryton-save'),
            Button('Next', 'loan_select_contracts', 'tryton-go-next',
                default=True)])
    change_basic_loan_data_next = StateTransition()
    loan_select_contracts = StateView('endorsement.loan.select_contracts',
        'endorsement_loan.select_contracts_view_form', [
            Button('Previous', 'display_updated_payments',
                'tryton-go-previous'),
            Button('Suspend', 'suspend', 'tryton-save'),
            Button('Next', 'loan_endorse_selected_contracts', 'tryton-go-next',
                default=True)])
    loan_endorse_selected_contracts = StateTransition()

    preview_loan = StateView('endorsement.start.preview_loan',
        'endorsement_loan.preview_loan_view_form', [
            Button('Summary', 'summary', 'tryton-go-previous'),
            Button('Cancel', 'cancel', 'tryton-cancel'),
            Button('Apply', 'apply_endorsement', 'tryton-go-next',
                default=True),
            ])

    def get_endorsed_object(self, endorsement_part):
        if endorsement_part.kind == 'loan':
            return self.select_endorsement.loan
        return super(StartEndorsement, self).get_endorsed_object(
            endorsement_part)

    def set_main_object(self, endorsement):
        if endorsement.__name__ == 'endorsement.loan':
            endorsement.loan = self.select_endorsement.loan
        else:
            super(StartEndorsement, self).set_main_object(endorsement)

    def transition_start(self):
        result = super(StartEndorsement, self).transition_start()
        endorsement = getattr(self.select_endorsement, 'endorsement', None)
        if endorsement and endorsement.loans:
            self.select_endorsement.loan = endorsement.loans[0].id
        return result

    def default_select_endorsement(self, name):
        result = super(StartEndorsement, self).default_select_endorsement(name)
        pool = Pool()
        Contract = pool.get('contract')
        active_model = Transaction().context.get('active_model')
        if active_model == 'contract':
            contract = Contract(Transaction().context.get('active_id'))
            if contract.is_loan:
                if len(contract.used_loans) == 1:
                    result['loan'] = contract.used_loans[0].id
        elif active_model == 'loan':
            result['loan'] == Transaction().context.get('active_id')
        return result

    def default_change_basic_loan_data(self, name):
        ChangeBasicLoanData = Pool().get('endorsement.loan.change_basic_data')
        result = ChangeBasicLoanData.get_state_view_default_values(self,
            'loan.loan_simple_view_form', 'loan', 'change_basic_loan_data',
            'loan_fields')
        result['loan'] = self.select_endorsement.loan.id
        return result

    def transition_change_basic_loan_data_previous(self):
        self.end_current_part('change_basic_loan_data')
        return self.get_state_before('change_basic_loan_data')

    def transition_calculate_updated_payments(self):
        self.end_current_part('change_basic_loan_data')
        return 'display_updated_payments'

    def default_display_updated_payments(self, name):
        current_loan = self.change_basic_loan_data.current_value[0]
        new_loan = self.change_basic_loan_data.new_value[0]
        new_loan.increments, new_loan.payments = [], []
        new_loan.calculate_increments()

        return {
            'loan': current_loan.id,
            'current_payments': [x.id for x in current_loan.payments],
            'new_payments': [
                dict([(x, getattr(payment, x, None))
                        for x in PAYMENT_FIELDS])
                for payment in new_loan.calculate_payments()]
            }

    def default_loan_select_contracts(self, name):
        Contract = Pool().get('contract')
        current_loan = self.change_basic_loan_data.current_value[0]
        possible_contracts = Contract.search([
                ('covered_elements.options.loan_shares.loan', '=',
                    current_loan)])
        selected_contracts = [x.id for x in self.endorsement.contracts]
        if not selected_contracts and self.select_endorsement.contract:
            selected_contracts = [self.select_endorsement.contract.id]
        return {
            'possible_contracts': [x.id for x in possible_contracts],
            'selected_contracts': selected_contracts,
            }

    def transition_loan_endorse_selected_contracts(self):
        ContractEndorsement = Pool().get('endorsement.contract')
        new_loan = self.change_basic_loan_data.new_value[0]
        current_loan = self.change_basic_loan_data.current_value[0]
        to_delete, to_create = [], []
        for contract_endorsement in self.endorsement.contract_endorsements:
            if (contract_endorsement.contract
                    not in self.loan_select_contracts.selected_contracts):
                if not contract_endorsement.apply_values:
                    to_delete.append(contract_endorsement)
        for contract in self.loan_select_contracts.selected_contracts:
            if contract in self.endorsement.contracts:
                continue
            to_create.append({
                    'endorsement': self.endorsement.id,
                    'contract': contract.id,
                    })
            if new_loan.funds_release_date != current_loan.funds_release_date:
                if current_loan.funds_release_date == contract.start_date:
                    oldest_loan = min([x.funds_release_date
                            for x in contract.used_loans
                            if x.id != current_loan.id] +
                        new_loan.funds_release_date)
                    if oldest_loan != contract.start_date:
                        to_create[-1]['values'] = {
                            'start_date': oldest_loan,
                            }
        if to_delete:
            ContractEndorsement.delete(to_delete)
        if to_create:
            ContractEndorsement.create(to_create)
        return 'change_basic_loan_data_next'

    def transition_change_basic_loan_data_next(self):
        return self.get_next_state('change_basic_loan_data')

    def default_preview_loan(self, name):
        LoanPreview = Pool().get('endorsement.start.preview_loan')
        preview_values = self.endorsement.extract_preview_values(
            LoanPreview.extract_endorsement_preview)
        return LoanPreview.init_from_preview_values(preview_values)

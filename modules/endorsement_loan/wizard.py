from collections import defaultdict
import datetime

from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.wizard import StateView, Button, StateTransition
from trytond.pyson import Eval, Bool

from trytond.modules.cog_utils import fields, model, coop_date
from trytond.modules.endorsement import EndorsementWizardStepBasicObjectMixin
from trytond.modules.endorsement import EndorsementWizardPreviewMixin
from trytond.modules.endorsement import EndorsementWizardStepMixin

PAYMENT_FIELDS = ['kind', 'number', 'start_date', 'begin_balance',
    'amount', 'principal', 'interest', 'outstanding_balance']

__metaclass__ = PoolMeta
__all__ = [
    'LoanChangeBasicData',
    'LoanDisplayUpdatedPayments',
    'LoanSelectContracts',
    'LoanContractDisplayer',
    'SelectLoanShares',
    'LoanShareSelector',
    'SharePerLoan',
    'SelectEndorsement',
    'PreviewLoanEndorsement',
    'PreviewContractPayments',
    'ContractPreview',
    'ContractPreviewPayment',
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

    selected_contracts = fields.One2Many(
        'endorsement.loan.select_contracts.contract', None,
        'Contracts to update')


class LoanContractDisplayer(model.CoopView):
    'Contract Displayer for the LoanSelectContracts view'

    __name__ = 'endorsement.loan.select_contracts.contract'

    contract = fields.Many2One('contract', 'Contract', readonly=True)
    endorsement = fields.Many2One('endorsement', 'Endorsement',
        states={'invisible': True}, readonly=True)
    current_end_date = fields.Date('Current End Date', readonly=True)
    current_start_date = fields.Date('Current Start Date', readonly=True)
    new_end_date = fields.Date('New End Date', readonly=True)
    new_start_date = fields.Date('New Start Date', states={
            'readonly': ~Eval('to_update', False)})
    to_update = fields.Boolean('To Update')

    @fields.depends('to_update', 'new_start_date', 'contract', 'endorsement')
    def _on_change(self):
        if not self.to_update:
            return {
                'new_end_date': None,
                'new_start_date': None,
                }
        contract_loans = set(self.contract.used_loans)
        endorsed_loans = set(self.endorsement.loans)
        contract_loans -= endorsed_loans

        max_loan_end = datetime.date.min
        if contract_loans:
            max_loan_end = max([loan.end_date for loan in contract_loans])

        for loan_endorsement in self.endorsement.loan_endorsements:
            loan = loan_endorsement.loan
            for k, v in loan_endorsement.values.iteritems():
                # TODO : Make it cleaner
                setattr(loan, k, v)
            loan.simulate()
            last_increment = loan.increments[-1]
            last_increment.loan = loan
            max_loan_end = max(max_loan_end,
                last_increment.on_change_with_end_date())
        result = {
            'new_start_date': self.new_start_date or self.contract.start_date,
            'new_end_date': coop_date.add_day(max_loan_end, -1),
            }
        return result

    on_change_to_update = _on_change
    on_change_new_start_date = _on_change


class SelectLoanShares(EndorsementWizardStepMixin, model.CoopView):
    'Select Loan Shares'

    __name__ = 'contract.covered_element.add_option.loan_shares'

    loan_share_selectors = fields.One2Many(
        'contract.covered_element.add_option.loan_share_selector', None,
        'New Loan Shares')
    shares_per_loan = fields.One2Many(
        'contract.covered_element.add_option.share_per_loan', None,
        'Shares per loan')

    @fields.depends('shares_per_loan', 'loan_share_selectors')
    def on_change_shares_per_loan(self):
        selector_values, share_values = [], []
        for share_per_loan in self.shares_per_loan:
            if share_per_loan.share is None:
                continue
            for selector in self.loan_share_selectors:
                if selector.loan != share_per_loan.loan:
                    continue
                if selector.new_share != share_per_loan.share:
                    selector_values.append({
                            'new_share': share_per_loan.share,
                            'id': selector.id,
                            })
            share_values.append({'share': None, 'id': share_per_loan.id})
        result = {'shares_per_loan': {'update': share_values}}
        if selector_values:
            result['loan_share_selectors'] = {
                'update': selector_values}
        return result

    @staticmethod
    def update_dict(to_update, key, value):
        # TODO : find a cleaner endorsement class detection
        to_update[key] = to_update[key + '_endorsement'] = None
        if hasattr(value, 'get_endorsed_record'):
            to_update[key + '_endorsement'] = value.id
        else:
            to_update[key] = value.id
        to_update[key + '_name'] = value.rec_name

    @classmethod
    def update_default_values(cls, wizard, base_endorsement, default_values):
        # Base_endorsement may be the current new endorsement. But we also have
        # to look in wizard.endorsement.contract_endorsements to detect other
        # contracts that may be modified
        if not base_endorsement.id:
            # New endorsement, no need to look somewhere else.
            all_endorsements = [base_endorsement]
        else:
            all_endorsements = list(wizard.endorsement.contract_endorsements)
        pool = Pool()
        LoanShareEndorsement = pool.get('endorsement.loan.share')
        effective_date = wizard.select_endorsement.effective_date
        selectors, template, all_loans = [], {}, set()
        for endorsement in all_endorsements:
            updated_struct = endorsement.updated_struct
            loans = set(list(endorsement.contract.used_loans) + [
                    x.loan for x in wizard.endorsement.loan_endorsements])
            if getattr(wizard.select_endorsement, 'loan', None):
                loans.add(wizard.select_endorsement.loan)
            all_loans |= loans
            template['contract'] = endorsement.contract.id
            for covered_element, values in (
                    updated_struct['covered_elements'].iteritems()):
                cls.update_dict(template, 'covered_element', covered_element)
                for option, o_values in values['options'].iteritems():
                    cls.update_dict(template, 'option', option)
                    for loan in [x for x in loans
                            if x not in o_values['loan_shares']]:
                        o_values['loan_shares'][loan] = {}
                    for loan, shares in o_values['loan_shares'].iteritems():
                        template['loan'] = loan.id
                        template['previous_share'] = None
                        sorted_list = sorted([x['instance'] for x in shares],
                            key=lambda x: x.start_date or
                            datetime.date.min)
                        selector = template.copy()
                        if not shares:
                            selectors.append(selector)
                            continue
                        for idx, loan_share in enumerate(sorted_list):
                            if ((loan_share.start_date or datetime.date.min) <
                                    effective_date):
                                template['previous_share'] = loan_share.share
                                continue
                            selector = template.copy()
                            if (loan_share.start_date == effective_date and
                                    isinstance(loan_share,
                                        LoanShareEndorsement)):
                                selector['new_share'] = loan_share.share
                                selector['loan_share_endorsement'] = \
                                    loan_share.id
                                if idx != len(sorted_list) - 1:
                                    future = sorted_list[idx + 1]
                                    selector['future_share'] = future.share
                                    if (isinstance(future,
                                                LoanShareEndorsement) and
                                            future.action == 'remove'):
                                        selector['override_future'] = True
                            else:
                                selector['previous_share'] = loan_share.share
                            selectors.append(selector)
                            break
                        else:
                            selector['previous_share'] = loan_share.share
                            selectors.append(selector)
        return {'loan_share_selectors': sorted(selectors, key=lambda x:
                (x['covered_element'], x['loan'], x['option_name'])),
            'shares_per_loan': [{'loan': x.id} for x in all_loans]}

    def update_endorsement(self, base_endorsement, wizard):
        # Base_endorsement may be the current new endorsement. But we also have
        # to look in wizard.endorsement.contract_endorsements to detect other
        # contracts that may be modified
        if not base_endorsement.id:
            endorsements = {base_endorsement.contract.id: base_endorsement}
        else:
            endorsements = {x.contract.id: x
                for x in wizard.endorsement.contract_endorsements}
        pool = Pool()
        Endorsement = pool.get('endorsement.contract')
        CoveredElementEndorsement = pool.get(
            'endorsement.contract.covered_element')
        OptionEndorsement = pool.get(
            'endorsement.contract.covered_element.option')
        LoanShareEndorsement = pool.get('endorsement.loan.share')
        new_covered_elements, new_options, new_shares = {}, {}, []
        for elem in self.loan_share_selectors:
            if elem.new_share is None:
                continue
            endorsement = endorsements[elem.contract.id]
            if elem.option_endorsement:
                option_endorsement = elem.option_endorsement
            elif elem.option in new_options:
                option_endorsement = new_options[elem.option]
            else:
                option_endorsement = OptionEndorsement(action='update',
                    relation=elem.option.id, loan_shares=[])
                new_options[elem.option] = option_endorsement
                if elem.covered_element_endorsement:
                    ce_endorsement = elem.covered_element_endorsement
                elif elem.covered_element in new_covered_elements:
                    ce_endorsement = new_covered_elements[elem.covered_element]
                else:
                    ce_endorsement = CoveredElementEndorsement(
                        action='update', relation=elem.covered_element.id,
                        options=[])
                    new_covered_elements[elem.covered_element] = ce_endorsement
                    if endorsement.id:
                        ce_endorsement.contract_endorsement = endorsement
                    else:
                        endorsement.covered_elements.append(ce_endorsement)
                if ce_endorsement.id:
                    option_endorsement.covered_element_endorsement = \
                        ce_endorsement.id
                else:
                    ce_endorsement.options.append(option_endorsement)
            for loan_share in option_endorsement.loan_shares:
                if loan_share.loan == elem.loan:
                    loan_share.values['share'] = elem.new_share
                    break
            else:
                loan_share = LoanShareEndorsement(action='add', values={
                        'loan': elem.loan.id, 'share': elem.new_share,
                        'start_date': self.effective_date},
                    loan=elem.loan)
                new_shares.append(loan_share)
            if option_endorsement.id:
                loan_share.option_endorsement = option_endorsement.id
            else:
                option_endorsement.loan_shares.append(loan_share)
        if new_shares:
            LoanShareEndorsement.create([x._save_values for x in new_shares
                    if getattr(x, 'option_endorsement', None)])
        if new_options:
            OptionEndorsement.create([x._save_values
                    for x in new_options.itervalues()
                    if getattr(x, 'covered_element_endorsement', None)])
        if new_covered_elements:
            to_create = [x._save_values
                for x in new_covered_elements.itervalues()
                if getattr(x, 'contract_endorsement', None)]
            if to_create and len(to_create) == len(new_covered_elements):
                CoveredElementEndorsement.create(to_create)
            else:
                to_write, to_create = [], []
                for elem in endorsements:
                    if elem.id:
                        to_write += [[elem.id], elem._save_values]
                    else:
                        to_create.append(elem._save_values)
                if to_write:
                    Endorsement.write(*to_write)
                if to_create:
                    Endorsement.create(to_create)


class LoanShareSelector(model.CoopView):
    'Loan Share Selector'

    __name__ = 'contract.covered_element.add_option.loan_share_selector'

    contract = fields.Many2One('contract', 'Contract', readonly=True)
    covered_element = fields.Many2One('contract.covered_element',
        'Covered Element', readonly=True)
    covered_element_endorsement = fields.Many2One(
        'endorsement.contract.covered_element', 'Covered Element',
        readonly=True)
    covered_element_name = fields.Char('Covered Element', readonly=True)
    future_share = fields.Numeric('Future Share', digits=(5, 4),
        readonly=True)
    loan = fields.Many2One('loan', 'Loan', readonly=True)
    loan_share_endorsement = fields.Many2One('endorsement.loan.share',
        'Loan Share Endorsement', readonly=True)
    new_share = fields.Numeric('New Share', digits=(5, 4))
    option = fields.Many2One('contract.option', 'Option', readonly=True)
    option_endorsement = fields.Many2One(
        'endorsement.contract.covered_element.option', 'Option Endorsement',
        readonly=True)
    option_name = fields.Char('Option', readonly=True)
    override_future = fields.Boolean('Override Future', states={
            'readonly': ~Bool(Eval('future_share', False))})
    previous_share = fields.Numeric('Previous Share', digits=(5, 4),
        readonly=True)
    terminate_loan = fields.Boolean('Terminate Loan')


class SharePerLoan(model.CoopView):
    'Share per Loan'

    __name__ = 'contract.covered_element.add_option.share_per_loan'

    loan = fields.Many2One('loan', 'Loan', readonly=True)
    share = fields.Numeric('Share', digits=(5, 4))


class SelectEndorsement:
    __name__ = 'endorsement.start.select_endorsement'

    loan = fields.Many2One('loan', 'Loan', states={
            'invisible': ~Eval('is_loan')}, domain=[
            ('id', 'in', Eval('possible_loans'))],
        depends=['is_loan', 'possible_loans'])
    is_loan = fields.Boolean('Is Loan', states={'invisible': True})
    possible_loans = fields.Many2Many('loan', None, None, 'Possible Loans',
        states={'invisible': True})

    @fields.depends('endorsement_definition', 'loan', 'effective_date',
        'contract')
    def on_change_endorsement_definition(self):
        if not self.endorsement_definition:
            return {'is_loan': False}
        if self.endorsement_definition.is_loan:
            if self.loan:
                return {
                    'is_loan': True,
                    'effective_date': self.loan.funds_release_date,
                    }
            elif self.contract and len(self.contract.used_loans) == 1:
                return {
                    'is_loan': True,
                    'loan': self.contract.used_loans[0].id,
                    'effective_date':
                    self.contract.used_loans[0].funds_release_date,
                    }
            else:
                return {
                    'is_loan': True,
                    'effective_date': None,
                    }
        else:
            return {
                'is_loan': False,
                'loan': None,
                'effective_date': None,
                }

    @fields.depends('is_loan', 'contract')
    def on_change_with_loan(self):
        if self.is_loan:
            if not self.contract:
                return None
            if len(self.contract.used_loans) == 1:
                return self.contract.used_loans[0].id
        return None

    @fields.depends('contract')
    def on_change_with_possible_loans(self):
        if not self.contract:
            return []
        return [x.id for x in self.contract.used_loans]


class PreviewLoanEndorsement(EndorsementWizardPreviewMixin, model.CoopView):
    'Preview Loan Endorsement'

    __name__ = 'endorsement.start.preview_loan'

    loan = fields.Many2One('loan', 'Loan', readonly=True)
    currency_digits = fields.Integer('Currency Digits')
    currency_symbol = fields.Char('Currency Symbol')
    new_amount = fields.Numeric('New Amount', digits=(16,
            Eval('currency_digits', 2)), depends=['currency_digits'],
        readonly=True)
    new_payments = fields.One2Many('loan.payment', None, 'New Payments',
        readonly=True)
    old_amount = fields.Numeric('Current Amount', digits=(16,
            Eval('currency_digits', 2)), depends=['currency_digits'],
        readonly=True)
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


class PreviewContractPayments(EndorsementWizardPreviewMixin,
        model.CoopView):
    'Preview Contract Payments'

    __name__ = 'endorsement.start.preview_contract_payments'

    contract_previews = fields.One2Many(
        'endorsement.start.preview_contract_payments.contract', None,
        'Contracts', readonly=True)

    @classmethod
    def extract_endorsement_preview(cls, instance):
        pool = Pool()
        Loan = pool.get('loan')
        Contract = pool.get('contract')
        PremiumAmountPerPeriod = pool.get('contract.premium.amount.per_period')
        ContractPreviewPayment = pool.get(
            'endorsement.start.preview_contract_payments.payment')
        if isinstance(instance, Loan):
            return {}
        if isinstance(instance, Contract):
            payments = []
            for payment in PremiumAmountPerPeriod.search([
                        ('contract', '=', instance.id)]):
                new_payment = {x: getattr(payment, x)
                    for x in ContractPreviewPayment.fields_to_extract()}
                new_payment['contract'] = instance.id
                payments.append(new_payment)
            return {
                'id': instance.id,
                'currency_digits': instance.currency_digits,
                'currency_symbol': instance.currency_symbol,
                'payments': payments,
                }

    @classmethod
    def init_from_preview_values(cls, preview_values):
        contracts = defaultdict(lambda: {
                'currency_digits': 2,
                'currency_symbol': '',
                'old_contract_payments': [],
                'new_contract_payments': [],
                'old_contract_amount': 0,
                'new_contract_amount': 0,
                'contract': None,
                })
        for kind in ('old', 'new'):
            for key, value in preview_values[kind].iteritems():
                if not key.startswith('contract,'):
                    continue
                contract_preview = contracts[value['id']]
                contract_preview['currency_digits'] = \
                    value['currency_digits']
                contract_preview['currency_symbol'] = \
                    value['currency_symbol']
                contract_preview['contract'] = value['id']
                for elem in value['payments']:
                    elem['currency_digits'] = value['currency_digits']
                    elem['currency_symbol'] = value['currency_symbol']
                    contract_preview['%s_contract_payments' % kind].append(
                        elem)
                    contract_preview['%s_contract_amount' % kind] += \
                        elem['total']
        return {'contract_previews': contracts.values()}


class ContractPreview(model.CoopView):
    'Contract Preview'

    __name__ = 'endorsement.start.preview_contract_payments.contract'

    contract = fields.Many2One('contract', 'Contract', readonly=True)
    currency_digits = fields.Integer('Currency Digits')
    currency_symbol = fields.Char('Currency Symbol')
    new_contract_amount = fields.Numeric('New Contract Amount', digits=(16,
            Eval('currency_digits', 2)), depends=['currency_digits'],
        readonly=True)
    old_contract_amount = fields.Numeric('Current Contract Amount',
        digits=(16, Eval('currency_digits', 2)), depends=['currency_digits'],
        readonly=True)
    new_contract_payments = fields.One2Many(
        'endorsement.start.preview_contract_payments.payment', None,
        'New Contract Payments', readonly=True)
    old_contract_payments = fields.One2Many(
        'endorsement.start.preview_contract_payments.payment', None,
        'Current Contract Payments', readonly=True)
    all_new_payments = fields.One2Many(
        'endorsement.start.preview_contract_payments.payment', None,
        'All New Payments', readonly=True, states={'invisible': True})
    all_old_payments = fields.One2Many(
        'endorsement.start.preview_contract_payments.payment', None,
        'All Old Payments', readonly=True, states={'invisible': True})


class ContractPreviewPayment(model.CoopView):
    'Contract Preview Payment'

    __name__ = 'endorsement.start.preview_contract_payments.payment'

    amount = fields.Numeric('Amount', digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits'])
    contract = fields.Integer('Contract')
    fees = fields.Numeric('Fees', digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits'])
    untaxed_amount = fields.Numeric('Total', digits=(16,
            Eval('currency_digits', 2)), depends=['currency_digits'])
    tax_amount = fields.Numeric('Tax Amount', digits=(16,
            Eval('currency_digits', 2)), depends=['currency_digits'])
    total = fields.Numeric('Total', digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits'])
    period_start = fields.Date('Period Start')
    period_end = fields.Date('Period End')
    currency_digits = fields.Integer('Currency Digits')
    currency_symbol = fields.Char('Currency Symbol')

    @classmethod
    def fields_to_extract(cls):
        return ['amount', 'fees', 'untaxed_amount', 'tax_amount', 'total',
            'period_start', 'period_end', 'contract']


class StartEndorsement:
    __name__ = 'endorsement.start'

    change_basic_loan_data = StateView('endorsement.loan.change_basic_data',
        'endorsement_loan.change_basic_loan_data_view_form',
        [Button('Previous', 'change_basic_loan_data_previous',
                'tryton-go-previous'),
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Suspend', 'suspend', 'tryton-save'),
            Button('Next', 'calculate_updated_payments', 'tryton-go-next',
                default=True)])
    change_basic_loan_data_previous = StateTransition()
    calculate_updated_payments = StateTransition()
    display_updated_payments = StateView(
        'endorsement.loan.display_updated_payments',
        'endorsement_loan.display_updated_payments_view_form', [
            Button('Previous', 'change_basic_loan_data', 'tryton-go-previous'),
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Suspend', 'suspend', 'tryton-save'),
            Button('Next', 'loan_select_contracts', 'tryton-go-next',
                default=True)])
    change_basic_loan_data_next = StateTransition()
    loan_select_contracts = StateView('endorsement.loan.select_contracts',
        'endorsement_loan.select_contracts_view_form', [
            Button('Previous', 'display_updated_payments',
                'tryton-go-previous'),
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Suspend', 'suspend', 'tryton-save'),
            Button('Next', 'loan_endorse_selected_contracts', 'tryton-go-next',
                default=True)])
    loan_endorse_selected_contracts = StateTransition()
    loan_share_update = StateView(
        'contract.covered_element.add_option.loan_shares',
        'endorsement_loan.update_loan_shares_view_form', [
            Button('Previous', 'loan_share_update_previous',
                'tryton-go-previous'),
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Suspend', 'suspend', 'tryton-save'),
            Button('Next', 'loan_share_update_next', 'tryton-go-next',
                default=True)])
    loan_share_update_previous = StateTransition()
    loan_share_update_next = StateTransition()
    preview_loan = StateView('endorsement.start.preview_loan',
        'endorsement_loan.preview_loan_view_form', [
            Button('Summary', 'summary', 'tryton-go-previous'),
            Button('Cancel', 'cancel', 'tryton-cancel'),
            Button('Apply', 'apply_endorsement', 'tryton-go-next',
                default=True),
            ])
    preview_contract_payments = StateView(
        'endorsement.start.preview_contract_payments',
        'endorsement_loan.preview_contract_payments_view_form', [
            Button('Summary', 'summary', 'tryton-go-previous'),
            Button('Cancel', 'cancel', 'tryton-cancel'),
            Button('Apply', 'apply_endorsement', 'tryton-go-next',
                default=True),
            ])

    @classmethod
    def __setup__(cls):
        super(StartEndorsement, cls).__setup__()
        cls._error_messages.update({
                'no_loan_share_on_new_coverage':
                'The following coverages have no loan share :\n  %s',
                })

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
            'loan.loan_simple_view_form', 'loan',
            'change_basic_loan_data', 'loan_fields')
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
        new_loan.calculate()

        return {
            'loan': current_loan.id,
            'current_payments': [x.id for x in current_loan.payments],
            'new_payments': [
                dict([(x, getattr(payment, x, None)) for x in PAYMENT_FIELDS])
                for payment in new_loan.payments]
            }

    def default_loan_select_contracts(self, name):
        Contract = Pool().get('contract')
        current_loan = self.change_basic_loan_data.current_value[0]
        possible_contracts = Contract.search([
                ('covered_elements.options.loan_shares.loan', '=',
                    current_loan)])
        contract_displayers = []
        for contract_endorsement in self.endorsement.contract_endorsements:
            contract = contract_endorsement.contract
            contract_displayers.append({
                    'contract': contract.id,
                    'to_update': True,
                    'endorsement': self.endorsement.id,
                    'current_start_date': contract.start_date,
                    'new_start_date': contract_endorsement.values.get(
                        'start_date', contract.start_date),
                    'current_end_date': contract.end_date,
                    'new_end_date': contract_endorsement.values.get(
                        'end_date', contract.end_date),
                    })
            possible_contracts.pop(contract)
        for contract in possible_contracts:
            contract_displayers.append({
                    'contract': contract.id,
                    'to_update': False,
                    'endorsement': self.endorsement.id,
                    'current_start_date': contract.start_date,
                    'current_end_date': contract.end_date,
                    })
        return {
            'selected_contracts': contract_displayers,
            }

    def transition_loan_endorse_selected_contracts(self):
        ContractEndorsement = Pool().get('endorsement.contract')
        to_create, to_write, to_delete = [], [], {}

        for contract_endorsement in self.endorsement.contract_endorsements:
            to_delete[contract_endorsement.contract.id] = \
                contract_endorsement
        for displayer in self.loan_select_contracts.selected_contracts:
            if not displayer.to_update:
                continue
            elif displayer.contract in to_delete:
                endorsement = to_delete.pop(displayer.contract)
                to_write.append(endorsement)
            else:
                endorsement = ContractEndorsement(
                    endorsement=self.endorsement.id,
                    contract=displayer.contract.id, values={})
                to_create.append(endorsement)
            endorsement.values['start_date'] = displayer.new_start_date
            endorsement.values['end_date'] = displayer.new_end_date
        if to_delete:
            ContractEndorsement.delete(to_delete)
        if to_create:
            ContractEndorsement.create([x._save_values for x in to_create])
        if to_write:
            ContractEndorsement.write(*[x
                    for values in [[[instance], instance._save_values]
                        for instance in to_write]
                    for x in values])
        return 'change_basic_loan_data_next'

    def transition_change_basic_loan_data_next(self):
        return self.get_next_state('change_basic_loan_data')

    def default_loan_share_update(self, name):
        ContractEndorsement = Pool().get('endorsement.contract')
        endorsement_part = self.get_endorsement_part_for_state(
            'loan_share_update')
        endorsement_date = self.select_endorsement.effective_date
        result = {
            'endorsement_part': endorsement_part.id,
            'effective_date': endorsement_date,
            }
        endorsements = self.get_endorsements_for_state('loan_share_update')
        if not endorsements:
            if self.select_endorsement.contract:
                endorsements = [ContractEndorsement(definition=self.definition,
                        endorsement=self.endorsement,
                        contract=self.select_endorsement.contract)]
            else:
                return result
        SelectLoanShares = Pool().get(
            'contract.covered_element.add_option.loan_shares')
        result.update(SelectLoanShares.update_default_values(self,
                endorsements[0], result))
        return result

    def transition_loan_share_update_previous(self):
        self.end_current_part('loan_share_update')
        return self.get_state_before('loan_share_update')

    def transition_loan_share_update_next(self):
        shares_per_new_coverage = set()
        all_new_coverages = set()
        for elem in self.loan_share_update.loan_share_selectors:
            if not (elem.option_endorsement and
                    elem.option_endorsement.action == 'add'):
                continue
            if elem.option_endorsement in shares_per_new_coverage:
                continue
            if elem.new_share:
                shares_per_new_coverage.add(elem.option_endorsement)
            all_new_coverages.add(elem.option_endorsement)
        bad_options = all_new_coverages - shares_per_new_coverage
        if bad_options:
            self.raise_user_error('no_loan_share_on_new_coverage', (
                    '  \n'.join([x.rec_name for x in bad_options])))
        self.end_current_part('loan_share_update')
        return self.get_next_state('loan_share_update')

    def default_preview_loan(self, name):
        LoanPreview = Pool().get('endorsement.start.preview_loan')
        preview_values = self.endorsement.extract_preview_values(
            LoanPreview.extract_endorsement_preview)
        return LoanPreview.init_from_preview_values(preview_values)

    def default_preview_contract_payments(self, name):
        ContractPaymentPreview = Pool().get(
            'endorsement.start.preview_contract_payments')
        preview_values = self.endorsement.extract_preview_values(
            ContractPaymentPreview.extract_endorsement_preview)
        return ContractPaymentPreview.init_from_preview_values(preview_values)

    @classmethod
    def get_fields_to_get(cls, model, view_id):
        result = super(StartEndorsement, cls).get_fields_to_get(model, view_id)
        if model == 'loan' and 'payments' in result:
            result.remove('payments')
        return result

    @classmethod
    def get_new_instance_fields(cls, base_instance, fields):
        result = super(StartEndorsement, cls).get_new_instance_fields(
            base_instance, fields)
        if base_instance.__name__ != 'loan' or 'increments' not in fields:
            return result
        result['increments'] = [dict([
                    (fname, getattr(x, fname))
                    for fname in ('number_of_payments', 'deferal',
                        'number', 'rate', 'payment_amount', 'start_date',
                        'begin_balance', 'currency_symbol',
                        'currency_digits')])
            for x in Pool().get('loan.increment').browse(
                result['increments'])]
        return result

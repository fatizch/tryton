from collections import defaultdict
import datetime

from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.wizard import StateView, Button, StateTransition
from trytond.pyson import Eval, Bool, Len, If, Not

from trytond.modules.cog_utils import fields, model, utils, coop_date
from trytond.modules.endorsement import EndorsementWizardPreviewMixin
from trytond.modules.endorsement import EndorsementWizardStepMixin, \
    add_endorsement_step

PAYMENT_FIELDS = ['kind', 'number', 'start_date', 'begin_balance',
    'amount', 'principal', 'interest', 'outstanding_balance']

__metaclass__ = PoolMeta
__all__ = [
    'ExtraPremiumDisplayer',
    'NewExtraPremium',
    'ManageExtraPremium',
    'AddRemoveLoan',
    'AddRemoveLoanDisplayer',
    'ManageOptions',
    'OptionDisplayer',
    'ChangeLoanAtDate',
    'ChangeLoanDisplayer',
    'ChangeLoan',
    'ChangeLoanUpdatedPayments',
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


class ExtraPremiumDisplayer:
    __name__ = 'endorsement.contract.extra_premium.displayer'

    is_loan = fields.Boolean('Is Loan', readonly=True, states={
            'invisible': True})

    @classmethod
    def __setup__(cls):
        super(ExtraPremiumDisplayer, cls).__setup__()
        cls.extra_premium.context.update({
                'is_loan': Eval('is_loan', False)})
        cls.extra_premium.depends.append('is_loan')


class ManageExtraPremium:
    __name__ = 'endorsement.contract.manage_extra_premium'

    @classmethod
    def _extra_premium_fields_to_extract(cls):
        field_names = super(ManageExtraPremium,
            cls)._extra_premium_fields_to_extract()
        field_names.append('is_loan')
        return field_names

    @classmethod
    def create_displayer(cls, extra_premium, template):
        displayer = super(ManageExtraPremium, cls).create_displayer(
            extra_premium, template)
        pool = Pool()
        if template['option']:
            coverage = pool.get('contract.option')(template['option']).coverage
        elif template['option_endorsement']:
            coverage = pool.get('endorsement.contract.covered_element.option')(
                template['option_endorsement']).coverage
        displayer['extra_premium'][0]['is_loan'] = coverage.is_loan
        displayer['is_loan'] = coverage.is_loan
        return displayer


class NewExtraPremium:
    __name__ = 'endorsement.contract.new_extra_premium'

    is_loan = fields.Boolean('Is Loan', readonly=True, states={
            'invisible': True})

    @classmethod
    def __setup__(cls):
        super(NewExtraPremium, cls).__setup__()
        cls.new_extra_premium.context.update({
                'is_loan': Eval('is_loan', False)})
        cls.new_extra_premium.depends.append('is_loan')


class ManageOptions:
    __name__ = 'contract.manage_options'

    def _update_added(self, new_option, parent, existing_options, per_id):
        super(ManageOptions, self)._update_added(new_option, parent,
            existing_options, per_id)
        if not self.contract.is_loan:
            return
        good_option = [x for x in parent.options
            if x.coverage == new_option.coverage
            and x.manual_start_date == self.effective_date][0]
        if getattr(good_option, 'loan_shares', None):
            return
        LoanShare = Pool().get('loan.share')
        shares_per_loan = defaultdict(set)
        for share in [x for option in parent.options
                for x in getattr(option, 'loan_shares', [])]:
            if share.share == 0 or share.loan.end_date < self.effective_date:
                continue
            if ((share.start_date or datetime.date.min) < self.effective_date
                    < (share.end_date or datetime.date.max)):
                shares_per_loan[share.loan].add(share.share)
        new_shares = []
        for loan, shares in shares_per_loan.iteritems():
            if len(shares) > 1:
                continue
            new_shares.append(LoanShare(loan=loan, share=shares.pop(),
                    start_date=self.effective_date))
        good_option.loan_shares = new_shares


class OptionDisplayer:
    __name__ = 'contract.manage_options.option_displayer'

    @classmethod
    def _option_fields_to_extract(cls):
        to_extract = super(OptionDisplayer, cls)._option_fields_to_extract()
        # No need to extract extra_data, they will be overriden anyway
        to_extract['contract.option'] += ['loan_shares']
        to_extract['loan.share'] = ['loan', 'share', 'start_date', 'end_date']
        return to_extract

    def to_option(self):
        new_option = super(OptionDisplayer, self).to_option()
        if not getattr(new_option, 'loan_shares', None):
            return new_option
        new_shares = []
        for loan_share in new_option.loan_shares:
            if self.effective_date > getattr(loan_share, 'end_date',
                    datetime.date.max):
                continue
            loan_share.start_date = min(self.effective_date,
                loan_share.start_date or datetime.date.max)
            new_shares.append(loan_share)
        new_option.loan_shares = new_shares
        return new_option


class AddRemoveLoan(EndorsementWizardStepMixin, model.CoopView):
    'Add Remove Loan'

    __name__ = 'endorsement.loan.add_remove'

    loan_actions = fields.One2Many('endorsement.loan.add_remove.displayer',
        None, 'Loans')
    possible_contracts = fields.Many2Many('contract', None, None,
        'Possible Contracts', readonly=True)
    new_loan = fields.Many2One('loan', 'New Loan')

    @classmethod
    def view_attributes(cls):
        return super(AddRemoveLoan, cls).view_attributes() + [
            ('/form/group[@id="invisible"]', 'states', {'invisible': True})]

    @fields.depends('loan_actions', 'possible_contracts')
    def on_change_loan_actions(self):
        if not self.loan_actions or not self.possible_contracts:
            return

        def update_group(loan, contracts, modified):
            modified.previous_check = modified.checked
            if not modified.contract:
                for contract in contracts:
                    contract.checked = modified.checked
                    contract.previous_check = modified.previous_check
            else:
                loan.checked = any([x.checked for x in contracts])
                loan.previous_check = loan.checked

        new_displayers = []
        cur_loan, cur_contracts, modified = None, [], None
        for action in self.loan_actions:
            new_displayers.append(action)
            if not action.contract and not action.loan:
                continue
            if not action.contract:
                if modified:
                    update_group(cur_loan, cur_contracts, modified)
                    modified = None
                cur_loan, cur_contracts = action, []
            else:
                cur_contracts.append(action)
            if action.checked != action.previous_check:
                modified = action
        if modified:
            update_group(cur_loan, cur_contracts, modified)
        self.loan_actions = new_displayers

    @fields.depends('loan_actions', 'new_loan', 'possible_contracts')
    def on_change_new_loan(self):
        if self.new_loan.id in [x.loan.id
                for x in self.loan_actions if x.loan]:
            self.new_loan = None
            return

        Displayer = Pool().get('endorsement.loan.add_remove.displayer')
        displayers = list(self.loan_actions)
        displayers.append(Displayer(name=''))
        loan_action = Displayer(loan=self.new_loan, contract=None,
            existed_before=False, checked=True, previous_check=True)
        loan_action.name = loan_action.on_change_with_name()
        displayers.append(loan_action)
        for contract in self.possible_contracts:
            contract_displayer = Displayer(contract=contract,
                loan=self.new_loan, checked=True, previous_check=True,
                existed_before=False)
            contract_displayer.name = contract_displayer.on_change_with_name()
            displayers.append(contract_displayer)
        self.loan_actions = displayers
        self.new_loan = None

    @classmethod
    def get_methods_for_model(cls, model_name):
        methods = super(AddRemoveLoan, cls).get_methods_for_model(
            model_name)
        if model_name == 'contract':
            methods |= {'recalculate_premium_after_endorsement',
                'rebill_after_endorsement', 'reconcile_after_endorsement'}
        return methods

    @classmethod
    def get_draft_methods_for_model(cls, model_name):
        methods = super(AddRemoveLoan, cls).get_draft_methods_for_model(
            model_name)
        if model_name == 'contract':
            methods |= {'rebill_after_endorsement',
                'reconcile_after_endorsement'}
        return methods

    def step_default(self, field_names):
        pool = Pool()
        Contract = pool.get('contract')
        Displayer = pool.get('endorsement.loan.add_remove.displayer')
        defaults = super(AddRemoveLoan, self).step_default()
        all_contracts, all_loans, new_matches = set(), set(), {}
        for ctr_endorsement in self.wizard.endorsement.contract_endorsements:
            all_contracts.add(ctr_endorsement.contract)
            all_contracts |= set([
                    x for loan in ctr_endorsement.contract.loans
                    for x in loan.contracts])
            contract = Contract(ctr_endorsement.contract.id)
            utils.apply_dict(contract, ctr_endorsement.apply_values())
            new_matches[contract.id] = set([x.loan.id
                    for x in contract.ordered_loans if not x.id] +
                [x.id for x in contract.get_used_loans_at_date(
                        self.effective_date)])
            all_loans |= set(new_matches[contract.id])
        defaults['possible_contracts'] = [x.id for x in all_contracts]
        current_matches = {x.id: [l.id for l in x.get_used_loans_at_date(
                    self.effective_date)] for x in all_contracts}
        all_loans |= set(sum(current_matches.values(), []))
        displayers = []
        for loan in all_loans:
            if len(displayers):
                displayers.append(Displayer(name=''))
            new_displayer = Displayer(loan=loan, contract=None, checked=True,
                existed_before=False)
            displayers.append(new_displayer)
            for contract in all_contracts:
                ctr_displayer = Displayer(contract=contract, loan=loan)
                ctr_displayer.checked = loan in new_matches.get(contract.id,
                    current_matches[contract.id])
                ctr_displayer.existed_before = loan in current_matches[
                    contract.id]
                ctr_displayer.previous_check = ctr_displayer.checked
                ctr_displayer.name = ctr_displayer.on_change_with_name()
                if ctr_displayer.existed_before:
                    new_displayer.existed_before = True
                new_displayer.checked |= ctr_displayer.checked
                displayers.append(ctr_displayer)
            new_displayer.previous_check = new_displayer.checked
            new_displayer.name = new_displayer.on_change_with_name()
        defaults['loan_actions'] = [x._default_values for x in displayers]
        return defaults

    def step_update(self):
        pool = Pool()
        ContractEndorsement = pool.get('endorsement.contract')
        OrderedLoan = pool.get('contract-loan')
        Option = pool.get('contract.option')
        Share = pool.get('loan.share')
        endorsement = self.wizard.endorsement
        contracts, endorsements = {}, {}
        for ctr_endorsement in endorsement.contract_endorsements:
            contract = ctr_endorsement.contract
            endorsements[contract.id] = ctr_endorsement
            utils.apply_dict(contract, ctr_endorsement.apply_values())
            contracts[contract.id] = contract
        for contract in self.possible_contracts:
            if contract.id not in contracts:
                contracts[contract.id] = contract
        existing_loans = {x.id: [y.loan.id for y in x.ordered_loans]
            for x in self.possible_contracts}
        new_loans = defaultdict(set)
        for action in self.loan_actions:
            if not action.contract or not action.checked:
                continue
            new_loans[action.contract.id].add(action.loan.id)

        for contract_id in new_loans.iterkeys():
            contract = contracts[contract_id]
            removed = set(existing_loans[contract_id]) - new_loans[contract_id]
            added = new_loans[contract_id] - set(existing_loans[contract_id])
            contract.ordered_loans = [x for x in contract.ordered_loans
                if x.loan.id not in added and x.loan.id not in removed] + [
                OrderedLoan(loan=x) for x in added]

            # Sync loan shares
            for covered in contract.covered_elements:
                for option in covered.options:
                    if not getattr(option, 'id', None):
                        previous_shares = set({})
                    else:
                        previous_shares = {
                            x for x in Option(option.id).loan_shares
                            if x.loan.id not in removed}
                    new_shares = []
                    per_loan = defaultdict(list)
                    for share in option.loan_shares:
                        per_loan[share.loan.id].append(share)
                    for loan_id, shares in per_loan.iteritems():
                        if loan_id not in removed:
                            # Remove previously deleted loans
                            new_shares += [x for x in shares
                                if x.share
                                or x.start_date != self.effective_date]
                        else:
                            # Check the share is properly ended
                            zero_found = False
                            for share in shares:
                                if share.start_date == self.effective_date:
                                    share.share = 0
                                    zero_found = True
                                if not share.start_date or (share.start_date <=
                                        self.effective_date):
                                    new_shares.append(share)
                            if not zero_found:
                                new_shares.append(Share(share=0, loan=loan_id,
                                        start_date=self.effective_date))
                    previous_shares = previous_shares - set(new_shares)
                    option.loan_shares = new_shares + list(previous_shares)
                covered.options = list(covered.options)
            contract.covered_elements = list(contract.covered_elements)
            if contract_id not in endorsements:
                new_endorsement = ContractEndorsement(contract=contract_id)
                endorsements[contract_id] = new_endorsement
            self._update_endorsement(endorsements[contract_id],
                contract._save_values)
        endorsement.contract_endorsements = endorsements.values()
        endorsement.save()

    @classmethod
    def state_view_name(cls):
        return 'endorsement_loan.loan_add_remove_view_form'


class AddRemoveLoanDisplayer(model.CoopView):
    'Add Remove Loan Displayer'

    __name__ = 'endorsement.loan.add_remove.displayer'

    name = fields.Char('Name', readonly=True)
    loan = fields.Many2One('loan', 'Loan')
    contract = fields.Many2One('contract', 'Contract')
    checked = fields.Boolean('Checked', states={'invisible': ~Eval('loan')},
        depends=['loan'])
    existed_before = fields.Boolean('Existed Before')
    previous_check = fields.Boolean('Previous Check')

    @classmethod
    def view_attributes(cls):
        return super(AddRemoveLoanDisplayer, cls).view_attributes() + [
            ('/tree', 'colors', If(Eval('checked') != Eval('existed_before'),
                    If(Bool(Eval('checked')), 'green', 'red'), 'black'))]

    @fields.depends('loan', 'contract')
    def on_change_with_name(self):
        if self.contract:
            return '        ' + self.contract.rec_name
        return self.loan.rec_name


class ChangeLoanAtDate(EndorsementWizardStepMixin, model.CoopView):
    'Change Loan at Date'

    __name__ = 'endorsement.loan.change_any_date'

    current_loan = fields.Many2One('loan', 'Current Loan', states={
            'invisible': Len(Eval('possible_loans', [])) == 1},
        domain=[('id', 'in', Eval('possible_loans'))],
        depends=['possible_loans'])
    possible_loans = fields.Many2Many('loan', None, None, 'Possible Loans',
        readonly=True)
    all_increments = fields.One2Many('loan.increment', None, 'All increments',
        readonly=True)
    current_increments = fields.One2Many('loan.increment', None,
        'Current Increments', readonly=True)
    new_increments = fields.One2Many('loan.increment', None, 'New Increments')

    @classmethod
    def view_attributes(cls):
        return super(ChangeLoanAtDate, cls).view_attributes() + [(
                '/form/group[@id="invisible"]',
                'states',
                {'invisible': True})]

    @fields.depends('all_increments', 'current_increments', 'current_loan',
        'effective_date', 'new_increments')
    def on_change_current_loan(self):
        if self.new_increments:
            self.all_increments = [x for x in self.all_increments
                if x.loan != self.new_increments[0].loan
                or x.number is not None] + list(self.new_increments)
        if not self.current_loan:
            self.current_increments = []
            self.new_increments = []
            return
        current_increments, new_increments = [], []
        for increment in self.all_increments:
            if increment.loan != self.current_loan:
                continue
            if increment.number is not None:
                current_increments.append(increment)
            else:
                new_increments.append(increment)
        self.current_increments = current_increments
        self.new_increments = new_increments

    @fields.depends('current_loan', 'effective_date', 'new_increments')
    def on_change_new_increments(self):
        if not self.new_increments or getattr(self.new_increments[-1],
                'loan', None):
            return
        self.new_increments[-1].loan = self.current_loan
        if len(self.new_increments) > 1:
            new_start = coop_date.add_duration(
                self.new_increments[-2].end_date,
                self.new_increments[-2].payment_frequency, 1)
            new_rate = self.new_increments[-2].rate
        else:
            new_start = self.effective_date
            new_rate = self.current_loan.rate
        self.new_increments[-1].payment_frequency = \
            self.current_loan.payment_frequency
        self.new_increments[-1].rate = new_rate
        self.new_increments[-1].start_date = new_start
        self.new_increments[-1].currency = self.current_loan.currency
        self.new_increments[-1].currency_digits = \
            self.current_loan.currency_digits
        self.new_increments[-1].currency_symbol = \
            self.current_loan.currency_symbol
        self.new_increments[-1].manual = len(self.new_increments) == 1
        self.new_increments[-1].loan_state = 'draft'
        self.new_increments = list(self.new_increments)

    @classmethod
    def get_methods_for_model(cls, model_name):
        methods = super(ChangeLoanAtDate, cls).get_methods_for_model(
            model_name)
        if model_name == 'contract':
            methods |= {'recalculate_premium_after_endorsement',
                'rebill_after_endorsement', 'reconcile_after_endorsement'}
        return methods

    @classmethod
    def get_draft_methods_for_model(cls, model_name):
        methods = super(ChangeLoanAtDate, cls).get_draft_methods_for_model(
            model_name)
        if model_name == 'contract':
            methods |= {'rebill_after_endorsement',
                'reconcile_after_endorsement'}
        return methods

    def step_default(self, field_names):
        defaults = super(ChangeLoanAtDate, self).step_default()
        updated_loans = self.updated_loans(self.get_default_loans())
        defaults['possible_loans'] = [x.id for x in updated_loans.itervalues()]
        defaults['current_loan'] = defaults['possible_loans'][0]

        all_increments = []
        for loan in updated_loans.itervalues():
            for increment in sorted(loan.increments,
                    key=lambda x: x.start_date):
                self.update_increment_displayer(increment, loan)
                all_increments.append(increment)
        increments_fields = self._increments_fields_to_extract()
        defaults['all_increments'] = [model.dictionarize(x, increments_fields)
            for x in all_increments]
        return defaults

    def step_update(self):
        # Update all_increments
        self.on_change_current_loan()
        LoanEndorsement = Pool().get('endorsement.loan')
        endorsement_data = self.get_default_loans()
        updated_loans = self.updated_loans(endorsement_data)
        new_increments = {loan: [x for x in loan.increments
                if x.start_date < self.effective_date]
            for loan in self.possible_loans}
        modified = set()
        for increment in self.all_increments:
            if increment.number is None:
                new_increments[increment.loan].append(increment)
                modified.add(increment.loan.id)
        loan_endorsements = []
        for loan_id in modified:
            loan = updated_loans[loan_id]
            loan.increments = new_increments[loan]
            endorsement = endorsement_data[loan]
            if endorsement is None:
                endorsement = LoanEndorsement(loan=loan)
            self._update_endorsement(endorsement, loan._save_values)
            loan_endorsements.append(endorsement)
        if loan_endorsements:
            self.wizard.endorsement.loan_endorsements = loan_endorsements
            self.wizard.endorsement.save()

    def step_next(self):
        super(ChangeLoanAtDate, self).step_next()
        return 'display_updated_payments'

    def update_increment_displayer(self, increment, loan):
        # Force set for new increments
        if not getattr(increment, 'loan', None):
            increment.loan = loan
        if not getattr(increment, 'id', None):
            increment.id = None
        if not getattr(increment, 'loan_state', None):
            increment.loan_state = 'draft'
        if not getattr(increment, 'currency', None):
            increment.currency = loan.currency
            increment.currency_digits = loan.currency_digits
            increment.currency_symbol = loan.currency_symbol
        increment.calculated_amount = \
            increment.calculate_payment_amount()

    @classmethod
    def _increments_fields_to_extract(cls):
        return {'loan.increment': ['number', 'begin_balance', 'start_date',
                'end_date', 'loan', 'number_of_payments', 'rate',
                'payment_amount', 'payment_frequency', 'currency',
                'currency_symbol', 'currency_digits',
                'payment_frequency_string', 'deferral', 'deferral_string',
                'manual', 'id', 'loan_state', 'calculated_amount']}

    def get_default_loans(self):
        endorsement = self.wizard.endorsement
        existing_endorsements = {x.loan: x
            for x in endorsement.loan_endorsements}
        for contract_endorsement in endorsement.contract_endorsements:
            for loan in contract_endorsement.contract.loans:
                if loan not in existing_endorsements:
                    existing_endorsements[loan] = None
        return existing_endorsements

    def updated_loans(self, loan_dicts):
        loans = {}
        for loan, endorsement in loan_dicts.iteritems():
            if endorsement:
                utils.apply_dict(loan, endorsement.apply_values())
            loans[loan.id] = loan
        return loans

    @classmethod
    def state_view_name(cls):
        return 'endorsement_loan.loan_change_any_date_view_form'


class ChangeLoanDisplayer(model.CoopView):
    'Change Loan Displayer'

    __name__ = 'endorsement.loan.change.displayer'

    current_values = fields.One2Many('loan', None, 'Current Values',
        readonly=True)
    new_values = fields.One2Many('loan', None, 'New Values')
    loan_id = fields.Integer('Loan Id')
    loan_rec_name = fields.Char('Loan', readonly=True)

    @fields.depends('new_values')
    def on_change_with_loan_rec_name(self):
        return self.new_values[0].get_rec_name(None)


class ChangeLoan(EndorsementWizardStepMixin):
    'Change Loan Data'

    __name__ = 'endorsement.loan.change'

    loan_changes = fields.One2Many('endorsement.loan.change.displayer', None,
        'Loan Changes')

    @classmethod
    def view_attributes(cls):
        return super(ChangeLoan, cls).view_attributes() + [
            ('/form/group[@id="one_loan"]', 'states',
                {'invisible': Len(Eval('loan_changes', [])) != 1}),
            ('/form/group[@id="multiple_loan"]', 'states',
                {'invisible': Len(Eval('loan_changes', [])) == 1}),
            ]

    @classmethod
    def get_methods_for_model(cls, model_name):
        methods = super(ChangeLoan, cls).get_methods_for_model(
            model_name)
        if model_name == 'contract':
            methods |= {'recalculate_premium_after_endorsement',
                'rebill_after_endorsement', 'reconcile_after_endorsement'}
        return methods

    @classmethod
    def get_draft_methods_for_model(cls, model_name):
        methods = super(ChangeLoan, cls).get_draft_methods_for_model(
            model_name)
        if model_name == 'contract':
            methods |= {'rebill_after_endorsement',
                'reconcile_after_endorsement'}
        return methods

    @classmethod
    def _loan_fields_to_extract(cls):
        return {
            'loan': ['currency', 'rate', 'payment_frequency', 'order',
                'first_payment_date', 'funds_release_date',
                'kind', 'amount', 'number', 'company', 'increments',
                'duration', 'duration_unit', 'currency_symbol',
                'currency_digits', 'previous_frequency',
                'previous_release_date'],
            'loan.increment': ['number', 'begin_balance', 'start_date',
                'end_date', 'loan', 'number_of_payments', 'rate',
                'payment_amount', 'payment_frequency', 'deferral', 'manual',
                'id', 'loan_state', 'calculated_amount'],
            }

    @classmethod
    def update_default_values(cls, wizard, endorsement, default_values):
        loan_endorsements = {}
        if endorsement:
            loan_endorsements = {x.loan.id: x
                for x in endorsement.loan_endorsements}
        for loan_change, loan_id in [(x['new_values'][0], x['loan_id'])
                    for x in default_values['loan_changes']]:
            loan_change['state'] = 'draft'
            if loan_id in loan_endorsements:
                cur_changes = loan_endorsements[loan_id]
                loan_change.update(cur_changes.values)
                loan_change['increments'] = [x.values for x in
                    cur_changes.increments if x.action == 'add']
            for increment in loan_change['increments']:
                if increment.get('start_date', None) is not None:
                    increment['end_date'] = coop_date.add_duration(
                        increment['start_date'],
                        increment['payment_frequency'],
                        increment['number_of_payments'] - 1,
                        stick_to_end_of_month=True)
                increment['currency'] = loan_change['currency']
                increment['currency_symbol'] = loan_change['currency_symbol']
                increment['currency_digits'] = loan_change['currency_digits']
            loan_change['previous_frequency'] = loan_change[
                'payment_frequency']
            loan_change['previous_release_date'] = loan_change[
                'funds_release_date']

    def update_endorsement(self, base_endorsement, wizard):
        all_endorsements = {x.loan.id: x
            for x in wizard.endorsement.loan_endorsements}
        pool = Pool()
        LoanEndorsement = pool.get('endorsement.loan')
        Loan = pool.get('loan')

        # Check modifier loan dates, use contract.check_loan_dates once
        # we use the "standard" approach of modifying the instance
        ctr_endorsement = wizard.endorsement.contract_endorsements[0]
        base_date = ctr_endorsement.values.get('start_date',
            ctr_endorsement.contract.initial_start_date)
        bad_loans = [loan.loan_rec_name
            for loan in self.loan_changes
            if loan.new_values[0].funds_release_date != base_date]
        if bad_loans:
            ctr_endorsement.contract.raise_user_warning(
                ctr_endorsement.contract.rec_name, 'bad_loan_dates',
                ('\t\n'.join(bad_loans),))

        endorsements_to_save = []
        for loan_change in self.loan_changes:
            base_loan = Loan(loan_change.loan_id)
            if loan_change.loan_id in all_endorsements:
                loan_endorsement = all_endorsements[loan_change.loan_id]
            else:
                loan_endorsement = LoanEndorsement(values={},
                    loan=base_loan.id, endorsement=wizard.endorsement.id,
                    increments=[])
            to_apply = loan_change.new_values[0]._save_values
            self.pop_loan_fields(to_apply)
            base_loan.increments = []
            utils.apply_dict(base_loan, to_apply)
            self._update_endorsement(loan_endorsement, base_loan._save_values)
            if not loan_endorsement.clean_up():
                endorsements_to_save.append(loan_endorsement)
        wizard.endorsement.loan_endorsements = endorsements_to_save
        wizard.endorsement.save()

    def pop_loan_fields(self, loan_dict):
        loan_dict.pop('state', None)
        loan_dict.pop('payments', None)
        loan_dict.pop('loan_shares', None)
        loan_dict.pop('contracts', None)


class ChangeLoanUpdatedPayments(model.CoopView):
    'Change Loan Updated Payments'

    __name__ = 'endorsement.loan.change.updated_payments'

    current_payments = fields.One2Many('loan.payment', None,
        'Current Payments', readonly=True)
    loan_id = fields.Integer('Loan Id', states={'invisible': True})
    loan_rec_name = fields.Char('Loan')
    new_payments = fields.One2Many('loan.payment', None, 'New Payments',
        readonly=True)


class LoanDisplayUpdatedPayments(model.CoopView):
    'Display Updated Payments'

    __name__ = 'endorsement.loan.display_updated_payments'

    @classmethod
    def view_attributes(cls):
        return [
            ('/form/group[@id="one_loan"]', 'states',
                {'invisible': Len(Eval('loans', [])) != 1}),
            ('/form/group[@id="multiple_loan"]', 'states',
                {'invisible': Len(Eval('loans', [])) == 1}),
            ]

    loans = fields.One2Many('endorsement.loan.change.updated_payments', None,
        'Loan Payments')


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
    new_start_date = fields.Date('New Start Date', readonly=True)
    to_update = fields.Boolean('To Update')

    @fields.depends('to_update', 'new_start_date', 'new_end_date', 'contract',
        'endorsement')
    def on_change_to_update(self):
        if not self.to_update:
            self.new_start_date = None
            self.new_end_date = None
            return

        if not self.new_start_date:
            self.new_start_date = self.contract.start_date
        pool = Pool()
        Contract = pool.get('contract')
        Endorsement = pool.get('endorsement')
        ContractEndorsement = pool.get('endorsement.contract')
        contract_id = self.contract.id
        endorsement_id = self.endorsement.id
        add_endorsement = False
        if contract_id not in [x.id for x in self.endorsement.contracts]:
            add_endorsement = True

        with Transaction().new_cursor():
            try:
                if add_endorsement:
                    ContractEndorsement(contract=contract_id,
                        endorsement=endorsement_id, values={}).save()

                _endorsement = Endorsement(endorsement_id)
                _contract_endorsement = [x
                    for x in _endorsement.contract_endorsements
                    if x.contract.id == contract_id][0]
                _contract_endorsement.values.pop('end_date', None)
                _contract_endorsement.values['start_date'] = \
                    self.new_start_date
                Endorsement.soft_apply([_endorsement])
                _contract = Contract(contract_id)
                _contract.calculate()
                new_end_date = _contract.end_date
            finally:
                Transaction().cursor.rollback()

        self.new_end_date = new_end_date


class SelectLoanShares(EndorsementWizardStepMixin):
    'Select Loan Shares'

    __name__ = 'contract.covered_element.add_option.loan_shares'

    loan_share_selectors = fields.One2Many(
        'contract.covered_element.add_option.loan_share_selector', None,
        'New Loan Shares')
    shares_per_loan = fields.One2Many(
        'contract.covered_element.add_option.share_per_loan', None,
        'Shares per loan')

    @classmethod
    def view_attributes(cls):
        return [('/form/group[@id="hidden"]', 'states', {'invisible': True})]

    @fields.depends('shares_per_loan', 'loan_share_selectors')
    def on_change_shares_per_loan(self):
        self.shares_per_loan = list(self.shares_per_loan)
        self.loan_share_selectors = list(self.loan_share_selectors)
        for share_per_loan in self.shares_per_loan:
            if share_per_loan.share is None:
                continue
            for selector in self.loan_share_selectors:
                if selector.loan != share_per_loan.loan:
                    continue
                if selector.new_share != share_per_loan.share:
                    selector.new_share = share_per_loan.share
            share_per_loan.share = None

    @classmethod
    def get_methods_for_model(cls, model_name):
        methods = super(SelectLoanShares, cls).get_methods_for_model(
            model_name)
        if model_name == 'contract':
            methods |= {'recalculate_premium_after_endorsement',
                'rebill_after_endorsement', 'reconcile_after_endorsement'}
        return methods

    @classmethod
    def get_draft_methods_for_model(cls, model_name):
        methods = super(SelectLoanShares, cls).get_draft_methods_for_model(
            model_name)
        if model_name == 'contract':
            methods |= {'rebill_after_endorsement',
                'reconcile_after_endorsement'}
        return methods

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
            loans = set(endorsement.contract.get_used_loans_at_date(
                    effective_date))
            for loan in getattr(endorsement, 'ordered_loans', []):
                if loan.action == 'remove':
                    loans.remove(loan.loan)
                elif loan.action == 'add':
                    loans.add(loan.loan)
            all_loans |= loans
            template['contract'] = endorsement.contract.id
            for covered_element, values in (
                    updated_struct['covered_elements'].iteritems()):
                cls.update_dict(template, 'covered_element', covered_element)
                for option, o_values in values['options'].iteritems():
                    if option.manual_end_date and (option.manual_end_date <
                            effective_date):
                        continue
                    cls.update_dict(template, 'option', option)
                    for loan in [x for x in loans
                            if x not in o_values['loan_shares']]:
                        o_values['loan_shares'][loan] = {}
                    for loan, shares in o_values['loan_shares'].iteritems():
                        if loan not in loans:
                            continue
                        template['loan'] = loan.id
                        template['previous_share'] = None
                        selector = template.copy()
                        if not shares:
                            selectors.append(selector)
                            continue
                        sorted_list = sorted([x['instance'] for x in shares],
                            key=lambda x: x.start_date or datetime.date.min)
                        selector = template.copy()
                        for idx, loan_share in enumerate(sorted_list):
                            if loan_share.share == 0:
                                continue
                            if (effective_date == (loan_share.start_date
                                        or endorsement.contract.start_date)
                                    and isinstance(loan_share,
                                        LoanShareEndorsement)):
                                selector['new_share'] = loan_share.share
                                selector['loan_share_endorsement'] = \
                                    loan_share.id
                                if idx == 0 and loan_share.relation:
                                    selector['previous_share'] = \
                                        loan_share.loan_share.share
                                elif idx > 0:
                                    selector['previous_share'] = \
                                        sorted_list[idx - 1].share
                                if idx != len(sorted_list) - 1:
                                    future = sorted_list[idx + 1]
                                    selector['future_share'] = future.share
                                    if (isinstance(future,
                                                LoanShareEndorsement) and
                                            future.action == 'remove'):
                                        selector['override_future'] = True
                                break
                            elif ((loan_share.start_date or datetime.date.min)
                                    < effective_date):
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
        effective_date = wizard.endorsement.effective_date
        pool = Pool()
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
                        endorsement.covered_elements = list(
                            endorsement.covered_elements) + [ce_endorsement]
                if ce_endorsement.id:
                    option_endorsement.covered_element_endorsement = \
                        ce_endorsement.id
                else:
                    ce_endorsement.options = list(ce_endorsement.options) + [
                        option_endorsement]
            for loan_share in option_endorsement.loan_shares:
                if loan_share.loan == elem.loan:
                    loan_share.values['share'] = elem.new_share
                    break
            else:
                existing_shares = []
                option = elem.option or elem.option_endorsement.option
                if option:
                    existing_shares = [x for x in option.loan_shares
                        if x.loan == elem.loan and effective_date == (
                            x.start_date or elem.contract.start_date)]
                if existing_shares:
                    # We just want to update the existing loan_share, no need
                    # to create another one
                    loan_share = LoanShareEndorsement(action='update',
                        relation=existing_shares[0].id, loan=None,
                        values={'share': elem.new_share})
                else:
                    loan_share = LoanShareEndorsement(action='add', values={
                            'loan': elem.loan.id, 'share': elem.new_share,
                            'start_date': self.effective_date},
                        loan=elem.loan)
                new_shares.append(loan_share)
            if option_endorsement.id:
                loan_share.option_endorsement = option_endorsement.id
            else:
                option_endorsement.loan_shares = list(
                    option_endorsement.loan_shares) + [loan_share]
        if new_shares:
            LoanShareEndorsement.create([x._save_values for x in new_shares
                    if getattr(x, 'option_endorsement', None)])
        if new_options:
            OptionEndorsement.create([x._save_values
                    for x in new_options.itervalues()
                    if getattr(x, 'covered_element_endorsement', None)])
        if new_covered_elements:
            CoveredElementEndorsement.create([x._save_values
                    for x in new_covered_elements.itervalues()
                    if getattr(x, 'contract_endorsement', None)])
        for endorsement in [x for x in endorsements.itervalues() if not x.id]:
            endorsement.save()


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

    @classmethod
    def view_attributes(cls):
        return super(LoanShareSelector, cls).view_attributes() + [
            ('/tree', 'colors', If(Bool(Eval('new_share', False)), 'green',
                    If(Not(Bool(Eval('previous_share', False))), 'blue',
                        'grey'))),
            ]


class SharePerLoan(model.CoopView):
    'Share per Loan'

    __name__ = 'contract.covered_element.add_option.share_per_loan'

    loan = fields.Many2One('loan', 'Loan', readonly=True)
    share = fields.Numeric('Share', digits=(5, 4))


class SelectEndorsement:
    __name__ = 'endorsement.start.select_endorsement'

    @fields.depends('endorsement_definition', 'effective_date', 'endorsement',
        'contract')
    def on_change_endorsement_definition(self):
        if self.endorsement:
            self.effective_date = self.endorsement.effective_date
        if self.endorsement_definition and self.endorsement_definition.is_loan:
            if self.contract and len(self.contract.used_loans) == 1:
                self.effective_date = \
                    self.contract.used_loans[0].funds_release_date


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
    def view_attributes(cls):
        return [
            ('/form/group[@id="one_contract"]', 'states',
                {'invisible': Len(Eval('contract_previews', [])) != 1}),
            ('/form/group[@id="multiple_contract"]', 'states',
                {'invisible': Len(Eval('contract_previews', [])) == 1}),
            ]

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

    change_loan_data = StateView('endorsement.loan.change',
        'endorsement_loan.loan_change_view_form', [
            Button('Previous', 'change_loan_data_previous',
                'tryton-go-previous'),
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Suspend', 'suspend', 'tryton-save'),
            Button('Next', 'calculate_updated_payments', 'tryton-go-next',
                default=True)])
    change_loan_data_previous = StateTransition()
    calculate_updated_payments = StateTransition()
    display_updated_payments = StateView(
        'endorsement.loan.display_updated_payments',
        'endorsement_loan.display_updated_payments_view_form', [
            Button('Previous', 'back_to_loan_state', 'tryton-go-previous'),
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Suspend', 'suspend', 'tryton-save'),
            Button('Next', 'loan_select_contracts', 'tryton-go-next',
                default=True)])
    back_to_loan_state = StateTransition()
    change_loan_data_next = StateTransition()
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
                'The following coverages have no loan share :\n\t%s',
                })

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

    def default_change_loan_data(self, name):
        ChangeLoan = Pool().get('endorsement.loan.change')
        endorsement_part = self.get_endorsement_part_for_state(
            'change_loan_data')
        contract = self.select_endorsement.contract
        fields_to_extract = ChangeLoan._loan_fields_to_extract()
        default_values = {
            'endorsement_part': endorsement_part.id,
            'loan_changes': [{
                    'loan_id': loan.id,
                    'loan_rec_name': loan.rec_name,
                    'current_values': [loan.id],
                    'new_values': [
                        model.dictionarize(loan, fields_to_extract)],
                    } for loan in contract.used_loans],
            }
        ChangeLoan.update_default_values(self, self.endorsement,
            default_values)
        return default_values

    def transition_change_loan_data_previous(self):
        self.change_loan_data.update_endorsement(None, self)
        return self.get_state_before('change_loan_data')

    def transition_calculate_updated_payments(self):
        self.change_loan_data.update_endorsement(None, self)
        return 'display_updated_payments'

    def transition_back_to_loan_state(self):
        return [x.endorsement_part.view
            for x in self.definition.ordered_endorsement_parts
            if x.endorsement_part.view in (
                'change_loan_data', 'change_loan_any_date')][0]

    def default_display_updated_payments(self, name):
        default_values = []
        for endorsement in self.endorsement.loan_endorsements:
            old_loan = endorsement.loan
            new_loan = old_loan.__class__(old_loan.id)
            utils.apply_dict(new_loan, endorsement.apply_values())
            new_loan.calculate()
            default_values.append({
                    'loan_id': old_loan.id,
                    'loan_rec_name': new_loan.rec_name,
                    'current_payments': [
                        {x: getattr(payment, x, None) for x in PAYMENT_FIELDS}
                        for payment in old_loan.payments],
                    'new_payments': [
                        {x: getattr(payment, x, None) for x in PAYMENT_FIELDS}
                        for payment in new_loan.payments],
                    })
        return {'loans': default_values}

    def default_loan_select_contracts(self, name):
        Contract = Pool().get('contract')
        all_loans = [x.id for x in self.endorsement.loans]
        possible_contracts = Contract.search([
                ('covered_elements.options.loan_shares.loan', 'in',
                    all_loans)])
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
            possible_contracts.remove(contract)
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

        per_contract = {x.contract.id: x for x in
            self.endorsement.contract_endorsements}
        to_save = []
        for displayer in self.loan_select_contracts.selected_contracts:
            if displayer.contract.id in per_contract:
                endorsement = per_contract[displayer.contract.id]
                if not displayer.to_update:
                    endorsement.values.pop('end_date', None)
                    if not endorsement.clean_up():
                        to_save.append(endorsement)
                else:
                    to_save.append(endorsement)
            else:
                if not displayer.to_update:
                    continue
                endorsement = ContractEndorsement(
                    endorsement=self.endorsement.id,
                    contract=displayer.contract.id, values={})
                to_save.append(endorsement)
            endorsement.values['end_date'] = displayer.new_end_date
        self.endorsement.contract_endorsements = to_save
        self.endorsement.save()
        return 'change_loan_data_next'

    def transition_change_loan_data_next(self):
        return self.get_next_state([x.endorsement_part.view
                for x in self.definition.ordered_endorsement_parts
                if x.endorsement_part.view in (
                    'change_loan_data', 'change_loan_any_date')][0])

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
                    '\t\n'.join([x.rec_name for x in bad_options])))
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

    def default_new_extra_premium(self, name):
        result = super(StartEndorsement, self).default_new_extra_premium(name)
        contracts = list(self.endorsement.contracts)
        if Transaction().context.get('active_model') == 'contract':
            contracts.append(Pool().get('contract')(
                    Transaction().context.get('active_id')))
        result['is_loan'] = result['new_extra_premium'][0]['is_loan'] = any([
                contract.is_loan for contract in contracts])
        return result

    def end_current_part(self, state_name):
        # Override because change_loan_at_date does not use automatically
        # calculated endorsement
        if state_name != 'change_loan_any_date':
            return super(StartEndorsement, self).end_current_part(state_name)
        state = getattr(self, state_name)
        state.update_endorsement(self.endorsement, self)

add_endorsement_step(StartEndorsement, ChangeLoanAtDate,
    'change_loan_any_date')

add_endorsement_step(StartEndorsement, AddRemoveLoan,
    'loan_add_remove')

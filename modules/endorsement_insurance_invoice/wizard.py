# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from trytond.exceptions import UserWarning
from trytond.i18n import gettext
from trytond.model.exceptions import ValidationError
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, Len, If
from trytond.transaction import Transaction

from trytond.modules.coog_core import model, coog_string, fields, utils
from trytond.modules.endorsement.wizard import EndorsementWizardStepMixin
from trytond.modules.endorsement.wizard import EndorsementRecalculateMixin
from trytond.modules.endorsement.wizard import add_endorsement_step

__all__ = [
    'BasicPreview',
    'RecalculateAndReinvoiceContract',
    'ChangeBillingInformation',
    'ChangeDirectDebitAccount',
    'ContractDisplayer',
    'NewCoveredElement',
    'NewOptionOnCoveredElement',
    'RemoveOption',
    'ModifyCoveredElementInformation',
    'ManageExtraPremium',
    'ChangeContractStartDate',
    'ChangeContractExtraData',
    'ChangeContractSubscriber',
    'TerminateContract',
    'VoidContract',
    'ManageOptions',
    'StartEndorsement',
    ]


class BasicPreview(metaclass=PoolMeta):
    __name__ = 'endorsement.start.preview_changes'

    previous_total_invoice_amount = fields.Numeric(
        'Previous total invoice amount',
        digits=(16, Eval('currency_digits', 2)), depends=['currency_digits'])
    new_total_invoice_amount = fields.Numeric('New total invoice amount',
        digits=(16, Eval('currency_digits', 2)), depends=['currency_digits'])
    currency_symbol = fields.Char('Currency Symbol')
    currency_digits = fields.Integer('Currency Digits')

    @classmethod
    def get_fields_to_get(cls):
        result = super(BasicPreview, cls).get_fields_to_get()
        result['contract'].add('total_invoice_amount')
        result['contract'].add('currency_digits')
        result['contract'].add('currency_symbol')
        return result

    @classmethod
    def init_from_preview_values(cls, preview_values):
        result = super(BasicPreview, cls).init_from_preview_values(
            preview_values)

        # TODO : manage multi_contract
        changes_old = list(preview_values['old'].values())[0]
        changes_new = list(preview_values['new'].values())[0]
        result['previous_total_invoice_amount'] = changes_old[
            'total_invoice_amount']
        result['new_total_invoice_amount'] = changes_new[
            'total_invoice_amount']
        result['currency_digits'] = changes_new['currency_digits']
        result['currency_symbol'] = changes_new['currency_symbol']
        return result


class RecalculateAndReinvoiceContract(EndorsementRecalculateMixin):
    'Recalculate and Reinvoice Contract'

    __name__ = 'endorsement.contract.recalculate_and_reinvoice'

    @classmethod
    def state_view_name(cls):
        return 'endorsement.recalculate_contract_view_form'

    @classmethod
    def get_methods_for_model(cls, model_name):
        Recalculate = Pool().get('endorsement.contract.recalculate')
        methods = Recalculate.get_methods_for_model(model_name)
        if model_name == 'contract':
            methods |= {'recalculate_premium_after_endorsement',
                'rebill_after_endorsement', 'reconcile_after_endorsement'}
        return methods

    @classmethod
    def get_draft_methods_for_model(cls, model_name):
        Recalculate = Pool().get('endorsement.contract.recalculate')
        methods = Recalculate.get_draft_methods_for_model(model_name)
        if model_name == 'contract':
            methods |= {'rebill_after_endorsement',
                'reconcile_after_endorsement'}
        return methods


class ChangeBillingInformation(EndorsementWizardStepMixin):
    'Change Billing Information'

    __name__ = 'contract.billing_information.change'

    contract = fields.Many2One('contract', 'Contract', states={
            'readonly': True})
    product = fields.Many2One('offered.product', 'Product', states={
            'invisible': True})
    subscriber = fields.Many2One('party.party', 'Subscriber', states={
            'invisible': True})
    new_billing_information = fields.One2Many('contract.billing_information',
        None, 'New Billing Information', size=1, domain=[
            ('billing_mode.billing_rules.product', '=', Eval('product')),
            ['OR',
                ('direct_debit', '=', False),
                ('direct_debit_account', '!=', None)],
            ], depends=['product'])
    previous_billing_information = fields.One2Many(
        'contract.billing_information', None, 'Previous Billing Information',
        readonly=True)
    other_contracts = fields.One2Many(
        'contract.billing_information.change.contract_displayer', None,
        'Other Contracts', states={
            'invisible': Len(Eval('other_contracts', [])) == 0})

    def get_other_contracts_party_clause(self):
        return ('subscriber', '=', self.subscriber.id)

    @fields.depends('contract', 'effective_date', 'new_billing_information',
        'other_contracts', 'previous_billing_information', 'subscriber')
    def on_change_new_billing_information(self):
        if not self.new_billing_information:
            return
        pool = Pool()
        Contract = pool.get('contract')
        Displayer = pool.get(
            'contract.billing_information.change.contract_displayer')
        new_info = self.new_billing_information[0]
        previous_bank_account = \
            self.previous_billing_information[0].direct_debit_account
        new_bank_account = (new_info.direct_debit_account or
            new_info.direct_debit_account_selector)
        if (not new_info.billing_mode or
                not new_info.billing_mode.direct_debit or
                not new_bank_account or
                not previous_bank_account or
                new_bank_account == previous_bank_account):
            self.other_contracts = []
            return
        possible_contracts = {}
        for contract in Contract.search([
                    self.get_other_contracts_party_clause(),
                    ('id', '!=', self.contract.id),
                    ('status', 'not in', ('quote', 'declined')),
                    ['OR', ('end_date', '=', None),
                        ('end_date', '>=', self.effective_date)],
                    ('billing_informations.direct_debit_account', '=',
                        previous_bank_account.id)]):
            for idx, cur_data in enumerate(reversed(
                        contract.billing_informations)):
                if cur_data.direct_debit and (cur_data.direct_debit_account ==
                        previous_bank_account):
                    possible_contracts[contract.id] = contract
                    break
                if (cur_data.date or datetime.date.min) < self.effective_date:
                    break
        if not possible_contracts:
            self.other_contracts = []
            return
        new_contracts = [Displayer(contract=x.contract,
                to_propagate=x.to_propagate)
            for x in self.other_contracts
            if x.contract.id in possible_contracts]
        new_contracts_id = [x.contract.id for x in new_contracts]
        new_contracts += [Displayer(contract=x, to_propagate='nothing')
            for x in possible_contracts.values()
            if x.id not in new_contracts_id]
        with Transaction().set_context(
                contract_revision_date=self.effective_date):
            self._update_displayers(new_contracts)
        self.other_contracts = new_contracts

    def _update_displayers(self, displayers):
        for d in displayers:
            d.contract_status = d.contract.status_string
            d.subscriber = d.contract.subscriber
            d.payer = d.contract.payer
            d.direct_debit_account = \
                d.contract.billing_information.direct_debit_account \
                if d.contract.billing_information else None

    @classmethod
    def state_view_name(cls):
        return 'endorsement_insurance_invoice.' + \
            'change_billing_information_view_form'

    @classmethod
    def get_methods_for_model(cls, model_name):
        methods = super(ChangeBillingInformation, cls).get_methods_for_model(
            model_name)
        if model_name == 'contract':
            methods |= {'recalculate_premium_after_endorsement',
                'rebill_after_endorsement', 'reconcile_after_endorsement'}
        return methods

    @classmethod
    def get_draft_methods_for_model(cls, model_name):
        methods = super(ChangeBillingInformation,
            cls).get_draft_methods_for_model(model_name)
        if model_name == 'contract':
            methods |= {'rebill_after_endorsement',
                'reconcile_after_endorsement'}
        return methods

    @classmethod
    def billing_information_fields(cls):
        return ['billing_mode', 'contract', 'direct_debit',
            'direct_debit_account', 'direct_debit_day',
            'direct_debit_day_selector', 'is_once_per_contract',
            'payment_term', 'possible_payment_terms', 'payer',
            'possible_payers', 'possible_billing_modes']

    @classmethod
    def direct_debit_account_only_fields(cls):
        return ['direct_debit_account', 'direct_debit_day',
            'direct_debit_day_selector', 'payer']

    def step_default(self, name):
        defaults = super(ChangeBillingInformation, self).step_default()
        base_endorsement = self.wizard.endorsement.contract_endorsements[0]
        contract = base_endorsement.contract
        base_instance = utils.get_good_version_at_date(contract,
                'billing_informations', self.effective_date, 'date')
        defaults.update({
                'contract': contract.id,
                'subscriber': base_endorsement.values['subscriber']
                if 'subscriber' in base_endorsement.values
                else contract.subscriber.id,
                'product': contract.product.id,
                })
        defaults['previous_billing_information'] = [base_instance.id]
        updated = None
        for endorsement in base_endorsement.billing_informations:
            endorsement.values['contract'] = contract.id
            if endorsement.action == 'update':
                updated = endorsement
            if endorsement.action != 'add':
                continue
            defaults['new_billing_information'] = [endorsement.values]
            break
        else:
            previous_values = self._get_default_values({}, base_instance,
                self.billing_information_fields())
            if updated:
                previous_values.update(updated.values)
            previous_values['date'] = self.effective_date
            defaults['new_billing_information'] = [previous_values]
        other_contracts = []
        for contract_id, contract_endorsement in \
                self._get_contracts().items():
            if contract_id == defaults['contract']:
                continue
            if not contract_endorsement.billing_informations:
                other_contracts.append({'contract': contract_id,
                        'to_propagate': 'nothing'})
            else:
                new_modification = [x
                    for x in contract_endorsement.billing_informations
                    if x.action in ('update', 'add')][0]
                if (new_modification.values !=
                        defaults['new_billing_information'][0]):
                    other_contracts.append({'contract': contract_id,
                            'to_propagate': 'bank_account'})
                else:
                    other_contracts.append({'contract': contract_id,
                            'to_propagate': 'everything'})
        defaults['other_contracts'] = other_contracts
        return defaults

    def step_update(self):
        pool = Pool()
        Warning = pool.get('res.user.warning')
        endorsement = self.wizard.select_endorsement.endorsement
        self.set_account_owner()
        self.do_update_endorsement(endorsement)
        dates = []
        for billing_information in self.contract.billing_informations:
            if billing_information.date and \
                    billing_information.date > self.effective_date:
                dates.append('%s %s' % (
                        billing_information.billing_mode.rec_name,
                        coog_string.translate_value(
                            billing_information, 'date')))
        if len(dates):
            key = str(self)
            if Warning.check(key):
                raise UserWarning(key, gettext(
                        'endorsement_insurance_invoice'
                        '.msg_billing_mode_existing',
                        dates='\n' + '\n'.join(dates)))
        endorsement.save()

    def add_owner_to_account(self, account, owner):
        pool = Pool()
        Warning = pool.get('res.user.warning')
        key = account.number
        if Warning.check(key):
            raise UserWarning(key, gettext(
                    'endorsement_insurance_invoice'
                    '.msg_payer_not_account_owner'))
        account.owners = list(account.owners) + [owner.id]
        account.save()

    def set_account_owner(self):
        new_info = self.new_billing_information[0]
        if not new_info.payer:
            return
        if new_info.direct_debit_account:
            if new_info.payer not in new_info.direct_debit_account.owners:
                self.add_owner_to_account(new_info.direct_debit_account,
                    new_info.payer)
            return
        if not new_info.direct_debit_account_selector:
            return
        if (new_info.payer in
                new_info.direct_debit_account_selector.owners):
            new_info.direct_debit_account = \
                new_info.direct_debit_account_selector
            new_info.direct_debit_account_selector = None
            return
        self.add_owner_to_account(new_info.direct_debit_account_selector,
            new_info.payer)
        new_info.direct_debit_account = new_info.direct_debit_account_selector
        new_info.direct_debit_account_selector = None

    def do_update_endorsement(self, master_endorsement):
        pool = Pool()
        ContractEndorsement = pool.get('endorsement.contract')
        BillingInformation = pool.get('contract.billing_information')
        contract_endorsements = self._get_contracts()

        master_contract = master_endorsement.contract_endorsements[0].contract
        new_info = self.new_billing_information[0]
        previous_account = self.previous_billing_information[
            0].direct_debit_account

        if (not new_info.direct_debit_account and
                new_info.billing_mode.direct_debit):
            raise ValidationError(gettext(
                    'endorsement_insurance_invoice'
                    '.msg_direct_debit_account_required'))

        values = new_info._save_values
        values.pop('contract', None)
        values.pop('direct_debit_account_selector', None)
        values.pop('search_all_direct_debit_account', None)
        values.pop('possible_billing_modes', None)
        if not new_info.billing_mode.direct_debit:
            for fname in self.direct_debit_account_only_fields():
                values.pop(fname, None)
        new_endorsements = []
        for contract, action in [(master_contract, 'everything')] + [
                (x.contract, x.to_propagate) for x in self.other_contracts]:

            endorsement = contract_endorsements.get(contract.id, None)

            # Retrieve endorsement's current version values
            old_values = endorsement.apply_values() if endorsement else {}

            # Clean up billing related values, as we are going to update them
            if 'billing_informations' in old_values:
                del old_values['billing_informations']

            # Apply current modifications on contract
            utils.apply_dict(contract, old_values)

            # Remove future billing informations
            contract_billing_informations = [x
                for x in contract.billing_informations
                if not x.date or x.date <= self.effective_date]

            if action == 'everything':
                if (contract_billing_informations[-1].date ==
                        self.effective_date):
                    # Update last billing_information, it matches the
                    # endorsement date
                    utils.apply_dict(contract_billing_informations[-1], values)
                else:
                    # Create a new billing information
                    contract_billing_informations.append(BillingInformation(
                            **values))
            elif action == 'bank_account':
                if (contract_billing_informations[-1].date ==
                        self.effective_date):
                    for fname in self.direct_debit_account_only_fields():
                        setattr(contract_billing_informations[-1], fname,
                            getattr(new_info, fname, None))
                elif (contract_billing_informations[-1].direct_debit_account ==
                        previous_account):
                    new_values = {x: getattr(contract_billing_informations[-1],
                            x, None)
                        for x in self.billing_information_fields()}
                    for fname in self.direct_debit_account_only_fields():
                        new_values[fname] = getattr(new_info, fname, None)
                    new_values['date'] = self.effective_date
                    contract_billing_informations.append(BillingInformation(
                            **new_values))
                for existing_info in contract.billing_informations:
                    if (not existing_info.date or
                            existing_info.date <= self.effective_date):
                        continue
                    contract_billing_informations.append(existing_info)
                    if existing_info.direct_debit_account == previous_account:
                        existing_info.direct_debit_account = \
                            new_info.direct_debit_account
            contract.billing_informations = contract_billing_informations

            if endorsement is None:
                endorsement = ContractEndorsement(contract=contract)

            # Auto update endorsement from modified contract
            self._update_endorsement(endorsement, contract._save_values)

            if not endorsement.clean_up():
                new_endorsements.append(endorsement)

        if not new_endorsements:
            new_endorsements = [master_endorsement.contract_endorsements[0]]

        master_endorsement.contract_endorsements = new_endorsements

    @classmethod
    def check_before_start(cls, select_screen):
        pool = Pool()
        ContractInvoice = pool.get('contract.invoice')
        cur_parameters = utils.get_good_version_at_date(
                select_screen.contract, 'billing_informations',
                select_screen.effective_date,
                'date') or select_screen.contract.billing_informations[0]
        last_modified_parameter = utils.get_last_version_modified_before(
            select_screen.contract.billing_informations, cur_parameters,
            less_than_key=lambda x: x.date or datetime.date.min,
            compare_key=lambda x: x.billing_mode.id
            if x.billing_mode else None,
            inclusive=True)
        if not last_modified_parameter:
            last_modified_parameter = \
                select_screen.contract.billing_informations[0]
        billing_mode = last_modified_parameter.billing_mode
        if select_screen.effective_date < utils.today():
            # Make sure an invoice exists at this date
            if not ContractInvoice.search([
                        ('contract', '=', select_screen.contract.id),
                        ('start', '=', select_screen.effective_date)]):
                raise ValidationError(gettext(
                        'endorsement_insurance_invoice'
                        '.msg_no_matching_invoice_date',
                        contract=select_screen.contract.rec_name,
                        effective_date=select_screen.effective_date))
        rrule, until = billing_mode.get_rrule(last_modified_parameter.date
            or select_screen.contract.start_date
            or select_screen.contract.initial_start_date,
            until=select_screen.effective_date)
        if datetime.datetime.combine(select_screen.effective_date,
                datetime.datetime.min.time()) not in rrule:
            if select_screen.effective_date != (last_modified_parameter.date or
                    select_screen.contract.start_date):
                cls.append_functional_error(
                    ValidationError(gettext(
                            'endorsement_insurance_invoice'
                            '.msg_unauthorized_date',
                            date=select_screen.effective_date,
                            mode=billing_mode.rec_name)))


class ChangeDirectDebitAccount(ChangeBillingInformation):
    'Change Direct Debit Account'

    __name__ = 'contract.direct_debit_account.change'

    @classmethod
    def __setup__(cls):
        super(ChangeDirectDebitAccount, cls).__setup__()
        cls.other_contracts.domain = [
            ('to_propagate', 'in', ('nothing', 'bank_account'))]

    @classmethod
    def state_view_name(cls):
        return 'endorsement_insurance_invoice.' + \
            'change_direct_debit_account_view_form'

    @classmethod
    def get_methods_for_model(cls, model_name):
        methods = super(ChangeDirectDebitAccount, cls).get_methods_for_model(
            model_name)
        if model_name == 'contract':
            methods.discard('recalculate_premium_after_endorsement')
            methods.discard('rebill_after_endorsement')
            methods.discard('reconcile_after_endorsement')
        return methods

    @classmethod
    def get_draft_methods_for_model(cls, model_name):
        methods = super(ChangeDirectDebitAccount,
            cls).get_draft_methods_for_model(model_name)
        if model_name == 'contract':
            methods.discard('rebill_after_endorsement')
            methods.discard('reconcile_after_endorsement')
        return methods

    @classmethod
    def check_before_start(cls, select_screen):
        super(ChangeDirectDebitAccount, cls).check_before_start(select_screen)
        cls.pop_functional_error(ValidationError)
        if not utils.get_good_version_at_date(
                select_screen.contract, 'billing_informations',
                select_screen.effective_date,
                'date').direct_debit:
            cls.append_functional_error(
                ValidationError(gettext(
                        'endorsement_insurance_invoice.msg_not_direct_debit')))
        if select_screen.effective_date < utils.today():
            cls.append_functional_error(
                ValidationError(gettext(
                        'endorsement_insurance_invoice.msg_no_past_date')))

    @classmethod
    def must_skip_step(cls, data_dict):
        contract = data_dict.get('contract', None)
        if not contract:
            return False
        if not utils.get_good_version_at_date(contract,
                'billing_informations',
                data_dict['_endorsement_effective_date'], 'date').direct_debit:
            return True
        return False


class ContractDisplayer(model.CoogView):
    'Contract Displayer'

    __name__ = 'contract.billing_information.change.contract_displayer'

    contract = fields.Many2One('contract', 'Contract', readonly=True)
    contract_status = fields.Char('Contract Status', readonly=True)
    to_propagate = fields.Selection([('nothing', 'Nothing'),
            ('bank_account', 'Bank Account'), ('everything', 'Everything')],
        'Propagate')
    payer = fields.Many2One('party.party', 'Payer', readonly=True)
    subscriber = fields.Many2One('party.party', 'Subscriber', readonly=True)
    direct_debit_account = fields.Many2One('bank.account',
        'Direct Debit Account', readonly=True)

    @classmethod
    def view_attributes(cls):
        return super(ContractDisplayer, cls).view_attributes() + [
            ('/tree', 'colors', If(Eval('to_propagate', '') == 'bank_account',
                    'green', If(Eval('to_propagate', '') == 'everything',
                        'blue', 'black')))]


class NewCoveredElement(metaclass=PoolMeta):
    __name__ = 'contract.covered_element.new'

    @classmethod
    def get_methods_for_model(cls, model_name):
        methods = super(NewCoveredElement, cls).get_methods_for_model(
            model_name)
        if model_name == 'contract':
            methods |= {'recalculate_premium_after_endorsement',
                'rebill_after_endorsement', 'reconcile_after_endorsement'}
        return methods

    @classmethod
    def get_draft_methods_for_model(cls, model_name):
        methods = super(NewCoveredElement, cls).get_draft_methods_for_model(
            model_name)
        if model_name == 'contract':
            methods |= {'rebill_after_endorsement',
                'reconcile_after_endorsement'}
        return methods


class NewOptionOnCoveredElement(metaclass=PoolMeta):
    'New Covered Element Option'
    __name__ = 'contract.covered_element.add_option'

    @classmethod
    def get_methods_for_model(cls, model_name):
        methods = super(NewOptionOnCoveredElement, cls).get_methods_for_model(
            model_name)
        if model_name == 'contract':
            methods |= {'recalculate_premium_after_endorsement',
                'rebill_after_endorsement', 'reconcile_after_endorsement'}
        return methods

    @classmethod
    def get_draft_methods_for_model(cls, model_name):
        methods = super(NewOptionOnCoveredElement,
            cls).get_draft_methods_for_model(model_name)
        if model_name == 'contract':
            methods |= {'rebill_after_endorsement',
                'reconcile_after_endorsement'}
        return methods


class RemoveOption(metaclass=PoolMeta):
    __name__ = 'contract.covered_element.option.remove'

    @classmethod
    def get_methods_for_model(cls, model_name):
        methods = super(RemoveOption, cls).get_methods_for_model(
            model_name)
        if model_name == 'contract':
            methods |= {'recalculate_premium_after_endorsement',
                'rebill_after_endorsement', 'reconcile_after_endorsement'}
        return methods

    @classmethod
    def get_draft_methods_for_model(cls, model_name):
        methods = super(RemoveOption, cls).get_draft_methods_for_model(
            model_name)
        if model_name == 'contract':
            methods |= {'rebill_after_endorsement',
                'reconcile_after_endorsement'}
        return methods


class ModifyCoveredElementInformation(metaclass=PoolMeta):
    __name__ = 'contract.covered_element.modify'

    @classmethod
    def get_methods_for_model(cls, model_name):
        methods = super(ModifyCoveredElementInformation,
            cls).get_methods_for_model(
            model_name)
        if model_name == 'contract':
            methods |= {'recalculate_premium_after_endorsement',
                'rebill_after_endorsement', 'reconcile_after_endorsement'}
        return methods

    @classmethod
    def get_draft_methods_for_model(cls, model_name):
        methods = super(ModifyCoveredElementInformation,
            cls).get_draft_methods_for_model(
            model_name)
        if model_name == 'contract':
            methods |= {'rebill_after_endorsement',
                'reconcile_after_endorsement'}
        return methods


class ManageExtraPremium(metaclass=PoolMeta):
    __name__ = 'endorsement.contract.manage_extra_premium'

    @classmethod
    def get_methods_for_model(cls, model_name):
        methods = super(ManageExtraPremium, cls).get_methods_for_model(
            model_name)
        if model_name == 'contract':
            methods |= {'recalculate_premium_after_endorsement',
                'rebill_after_endorsement', 'reconcile_after_endorsement'}
        return methods

    @classmethod
    def get_draft_methods_for_model(cls, model_name):
        methods = super(ManageExtraPremium, cls).get_draft_methods_for_model(
            model_name)
        if model_name == 'contract':
            methods |= {'rebill_after_endorsement',
                'reconcile_after_endorsement'}
        return methods


class ChangeContractStartDate(metaclass=PoolMeta):
    __name__ = 'endorsement.contract.change_start_date'

    @classmethod
    def get_methods_for_model(cls, model_name):
        methods = super(ChangeContractStartDate, cls).get_methods_for_model(
            model_name)
        if model_name == 'contract':
            methods |= {'recalculate_premium_after_endorsement',
                'rebill_after_endorsement', 'reconcile_after_endorsement'}
        return methods

    @classmethod
    def get_draft_methods_for_model(cls, model_name):
        methods = super(ChangeContractStartDate,
            cls).get_draft_methods_for_model(model_name)
        if model_name == 'contract':
            methods |= {'rebill_after_endorsement',
                'reconcile_after_endorsement'}
        return methods


class ChangeContractExtraData(metaclass=PoolMeta):
    __name__ = 'endorsement.contract.change_extra_data'

    @classmethod
    def get_methods_for_model(cls, model_name):
        methods = super(ChangeContractExtraData, cls).get_methods_for_model(
            model_name)
        if model_name == 'contract':
            methods |= {'recalculate_premium_after_endorsement',
                'rebill_after_endorsement', 'reconcile_after_endorsement'}
        return methods

    @classmethod
    def get_draft_methods_for_model(cls, model_name):
        methods = super(ChangeContractExtraData,
            cls).get_draft_methods_for_model(model_name)
        if model_name == 'contract':
            methods |= {'rebill_after_endorsement',
                'reconcile_after_endorsement'}
        return methods


class TerminateContract(metaclass=PoolMeta):
    'Terminate Contract'
    __name__ = 'endorsement.contract.terminate'

    @classmethod
    def get_methods_for_model(cls, model_name):
        methods = super(TerminateContract, cls).get_methods_for_model(
            model_name)
        if model_name == 'contract':
            methods |= {'recalculate_premium_after_endorsement',
                'rebill_after_endorsement', 'reconcile_after_endorsement'}
        return methods

    @classmethod
    def get_draft_methods_for_model(cls, model_name):
        methods = super(TerminateContract,
            cls).get_draft_methods_for_model(model_name)
        if model_name == 'contract':
            methods |= {'rebill_after_endorsement',
                'reconcile_after_endorsement'}
        return methods


class VoidContract(metaclass=PoolMeta):
    'Void Contract'
    __name__ = 'endorsement.contract.void'

    @classmethod
    def get_methods_for_model(cls, model_name):
        methods = super(VoidContract, cls).get_methods_for_model(
            model_name)
        if model_name == 'contract':
            methods |= {'recalculate_premium_after_endorsement',
                'rebill_after_endorsement', 'reconcile_after_endorsement'}
        return methods

    @classmethod
    def get_draft_methods_for_model(cls, model_name):
        methods = super(VoidContract,
            cls).get_draft_methods_for_model(model_name)
        if model_name == 'contract':
            methods |= {'rebill_after_endorsement',
                'reconcile_after_endorsement'}
        return methods


class ChangeContractSubscriber(metaclass=PoolMeta):
    __name__ = 'endorsement.contract.subscriber_change'

    @classmethod
    def get_methods_for_model(cls, model_name):
        methods = super(ChangeContractSubscriber, cls).get_methods_for_model(
            model_name)
        if model_name == 'contract':
            methods |= {'recalculate_premium_after_endorsement',
                'rebill_after_endorsement', 'reconcile_after_endorsement'}
        return methods

    @classmethod
    def get_draft_methods_for_model(cls, model_name):
        methods = super(ChangeContractSubscriber,
            cls).get_draft_methods_for_model(model_name)
        if model_name == 'contract':
            methods |= {'rebill_after_endorsement',
                'reconcile_after_endorsement'}
        return methods


class ManageOptions(metaclass=PoolMeta):
    __name__ = 'contract.manage_options'

    @classmethod
    def get_methods_for_model(cls, model_name):
        methods = super(ManageOptions, cls).get_methods_for_model(
            model_name)
        if model_name == 'contract':
            methods |= {'recalculate_premium_after_endorsement',
                'rebill_after_endorsement', 'reconcile_after_endorsement'}
        return methods

    @classmethod
    def get_draft_methods_for_model(cls, model_name):
        methods = super(ManageOptions,
            cls).get_draft_methods_for_model(model_name)
        if model_name == 'contract':
            methods |= {'rebill_after_endorsement',
                'reconcile_after_endorsement'}
        return methods


class StartEndorsement(metaclass=PoolMeta):
    __name__ = 'endorsement.start'


add_endorsement_step(StartEndorsement, ChangeBillingInformation,
    'change_billing_information')
add_endorsement_step(StartEndorsement, ChangeDirectDebitAccount,
    'change_direct_debit_account')
add_endorsement_step(StartEndorsement, RecalculateAndReinvoiceContract,
    'recalculate_and_reinvoice_contract')

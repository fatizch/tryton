# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval

from trytond.modules.coog_core import fields, utils, model
from trytond.modules.endorsement.wizard import EndorsementWizardStepMixin, \
    add_endorsement_step


__all__ = [
    'StartEndorsement',
    'ChangeContractClaimAccount',
    'ContractEndorsement',
    ]


class StartEndorsement(metaclass=PoolMeta):
    __name__ = 'endorsement.start'


class ChangeContractClaimAccount(EndorsementWizardStepMixin):
    'Change contract claim account'

    __name__ = 'endorsement.contract.change_claim_account'

    current_claim_account = fields.Many2One('bank.account',
        'Current Claim Account', readonly=True)
    subscriber = fields.Many2One('party.party', 'Subscriber', readonly=True)
    contract = fields.Many2One('contract', 'Contract', readonly=True)
    new_claim_account = fields.Many2One('bank.account', 'New Bank Account',
        domain=[('owners', '=', Eval('subscriber')),
            ['OR',
                ('start_date', '=', None),
                ('start_date', '<=', Eval('effective_date')),
                ],
            ['OR',
                ('end_date', '=', None),
                ('end_date', '>=', Eval('effective_date')),
                ],
            ], depends=['subscriber', 'effective_date'])
    current_claim_account = fields.Many2One('bank.account',
        'Current Claim Account', readonly=True)
    calculated_bank_account = fields.Many2One('bank.account',
        'Calculated Bank Account', readonly=True)
    other_contracts = fields.Many2Many('contract', None, None,
        'Other Contracts', domain=[('id', 'in', Eval('possible_contracts'))],
        states={'invisible': ~Eval('possible_contracts')},
        depends=['possible_contracts'])
    possible_contracts = fields.Many2Many('contract', None, None,
        'Possible Contracts', readonly=True)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._buttons.update({
                'reset_new_claim_account': {
                    'readonly': ~~Eval('new_claim_account'),
                    },
                'add_all_contracts': {
                    'invisible': ~Eval('possible_contracts'),
                    },
                'remove_all_contracts': {
                    'invisible': ~Eval('possible_contracts'),
                    'readonly': ~Eval('other_contracts'),
                    },
                })
        cls._error_messages.update({
                'missing_new_account':
                'Please enter the new bank account to use',
                })

    @model.CoogView.button_change('calculated_bank_account',
        'new_claim_account')
    def reset_new_claim_account(self):
        self.new_claim_account = self.calculated_bank_account

    @model.CoogView.button_change('possible_contracts')
    def add_all_contracts(self):
        self.other_contracts = list(self.possible_contracts)

    @model.CoogView.button_change('possible_contracts')
    def remove_all_contracts(self):
        self.other_contracts = []

    @fields.depends('contract', 'effective_date')
    def on_change_subscriber(self):
        self.calculated_bank_account = \
            self.contract._get_default_claim_bank_account(
                at_date=self.effective_date)

    def step_default(self, name):
        defaults = super().step_default()

        pool = Pool()
        Contract = pool.get('contract')
        endorsed_contracts = self.wizard.endorsement.contract_endorsements

        if not endorsed_contracts and self.wizard.select_endorsement.contract:
            contract_endorsement = Pool().get('endorsement.contract')(
                contract=self.wizard.select_endorsement.contract,
                endorsement=self.wizard.endorsement)
            contract_endorsement.save()
            endorsed_contracts = [contract_endorsement]

        assert endorsed_contracts
        effective_date = self.wizard.endorsement.effective_date

        # The "main" contract will be the first one, which should be the one
        # that was originally selected
        contract_endorsement = endorsed_contracts[0]
        contract = Contract(contract_endorsement.contract.id)
        calculated_bank_account = contract._get_default_claim_bank_account(
            at_date=effective_date)
        if calculated_bank_account:
            defaults['calculated_bank_account'] = calculated_bank_account.id
        version = utils.get_value_at_date(contract.extra_datas, effective_date)
        value = version.claim_bank_account
        if value is None:
            value = calculated_bank_account
        defaults['current_claim_account'] = value.id if value else None
        utils.apply_dict(contract, contract_endorsement.apply_values())
        new_version = utils.get_value_at_date(contract.extra_datas,
            effective_date)
        new_account = new_version.claim_bank_account or calculated_bank_account
        defaults['new_claim_account'] = new_account.id if new_account else None
        defaults['subscriber'] = contract.subscriber.id
        defaults['contract'] = contract.id

        defaults['possible_contracts'] = [x.id for x in Contract.search([
                    ('subscriber', '=', contract.subscriber.id),
                    ('id', '!=', contract.id),
                    ('status', 'in', ('active', 'hold', 'terminated'))])
            if x.claims_paid_to_subscriber]
        defaults['other_contracts'] = [x.contract.id
            for x in endorsed_contracts if x != contract_endorsement]
        return defaults

    def step_update(self):
        if not self.new_claim_account:
            self.raise_user_error('missing_new_account')
        ContractEndorsement = Pool().get('endorsement.contract')
        endorsement = self.wizard.endorsement

        endorsed_contracts = self.wizard.endorsement.contract_endorsements
        assert endorsed_contracts

        per_contract_id = {}
        for contract_endorsement in endorsed_contracts:
            self.clean_up_contract_endorsement(contract_endorsement)
            per_contract_id[contract_endorsement.contract.id] = \
                contract_endorsement

        new_endorsements = []
        for contract in [self.contract] + list(self.other_contracts):
            if contract.id in per_contract_id:
                contract_endorsement = per_contract_id[contract.id]
            else:
                contract_endorsement = ContractEndorsement(
                    contract=contract.id, endorsement=endorsement)
                # Required so that apply_values does not crash everywhere
                contract_endorsement.save()
            self.update_contract_endorsement(contract_endorsement)
            self._update_endorsement(contract_endorsement,
                contract_endorsement.contract._save_values)
            if not contract_endorsement.clean_up():
                new_endorsements.append(contract_endorsement)
        endorsement.contract_endorsements = new_endorsements
        endorsement.save()

    def clean_up_contract_endorsement(self, contract_endorsement):
        contract_endorsement.extra_datas = []

    def update_contract_endorsement(self, contract_endorsement):
        cur_version = utils.get_value_at_date(
            contract_endorsement.contract.extra_datas,
            self.effective_date)

        utils.apply_dict(contract_endorsement.contract,
            contract_endorsement.apply_values())

        assert self.new_claim_account

        save_value = self.new_claim_account
        if self.new_claim_account == self.calculated_bank_account:
            save_value = None

        if cur_version.claim_bank_account == save_value:
            return

        version = contract_endorsement.version_for_modification(
            self.effective_date)
        version.claim_bank_account = save_value

    @classmethod
    def state_view_name(cls):
        return 'claim.change_contract_claim_account_view_form'


class ContractEndorsement(metaclass=PoolMeta):
    __name__ = 'endorsement.contract'

    def _new_version_fields(self):
        fields = super()._new_version_fields()
        fields['contract.extra_data'].append('claim_bank_account')
        return fields


add_endorsement_step(StartEndorsement, ChangeContractClaimAccount,
    'change_contract_claim_account')

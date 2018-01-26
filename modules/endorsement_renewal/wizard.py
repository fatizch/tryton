# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from dateutil.relativedelta import relativedelta
from trytond.pool import Pool, PoolMeta
from trytond.modules.endorsement.wizard import \
    EndorsementWizardStepMixin, add_endorsement_step
from trytond.modules.coog_core import utils, fields

__metaclass__ = PoolMeta
__all__ = [
    'ContractRenew',
    'StartEndorsement',
    ]


class ContractRenew(EndorsementWizardStepMixin):
    'Renew Contract'

    __name__ = 'endorsement.contract.renew'

    current_start_date = fields.Date('Current Start Date', readonly=True)
    current_end_date = fields.Date('Current End Date', readonly=True)
    new_period_start_date = fields.Date('New Period Start Date', readonly=True)
    new_period_end_date = fields.Date('New Period End Date', readonly=True)

    @classmethod
    def __setup__(cls):
        super(ContractRenew, cls).__setup__()
        cls._error_messages.update({
                'not_renewable': 'The contract %s is not renewable ',
                'already_renewed': 'The contract %s is already renewed ',
                })

    @classmethod
    def get_methods_for_model(cls, model_name):
        methods = super(ContractRenew, cls).get_methods_for_model(
            model_name)
        if model_name == 'contract' and utils.is_module_installed(
                'endorsement_insurance_invoice'):
            methods |= {'recalculate_premium_after_endorsement',
                'rebill_after_endorsement', 'reconcile_after_endorsement'}
            methods -= {'calculate_activation_dates'}
        return methods

    @classmethod
    def get_draft_methods_for_model(cls, model_name):
        methods = super(ContractRenew, cls).get_draft_methods_for_model(
            model_name)
        if model_name == 'contract' and utils.is_module_installed(
                'endorsement_insurance_invoice'):
            methods |= {'rebill_after_endorsement',
                'reconcile_after_endorsement'}
        return methods

    def step_default(self, name):
        pool = Pool()
        Contract = pool.get('contract')
        defaults = super(ContractRenew, self).step_default()
        contracts = self._get_contracts()
        contract_id, endorsement = contracts.items()[0]
        contract = Contract(contract_id)
        new_period_start_date = contract.end_date + relativedelta(days=1)
        defaults['current_start_date'] = contract.start_date
        defaults['current_end_date'] = contract.end_date
        defaults['new_period_start_date'] = new_period_start_date
        defaults['new_period_end_date'] = \
            contract.get_end_date_from_given_start_date(new_period_start_date)
        return defaults

    def step_update(self):
        endorsement = self.wizard.endorsement
        self.add_renewal_endorsement(endorsement)
        endorsement.save()

    @classmethod
    def check_before_start(cls, select_screen):
        contract = select_screen.contract
        if not contract.is_renewable:
            cls.append_functional_error('not_renewable', (contract.rec_name,))
        elif contract.end_date != contract.activation_history[-1].end_date:
            cls.append_functional_error('already_renewed',
                (contract.rec_name,))

    @classmethod
    def add_renewal_endorsement(cls, endorsement):
        pool = Pool()
        HistoryEndorsement = pool.get(
            'endorsement.contract.activation_history')
        for c_endors in endorsement.contract_endorsements:
            if c_endors.activation_history:
                continue
            new_start_date = c_endors.contract.end_date + relativedelta(days=1)
            history_endorsement = HistoryEndorsement(action='add',
                values={
                    'start_date': new_start_date,
                    'end_date':
                    c_endors.contract.get_end_date_from_given_start_date(
                        new_start_date)})
            c_endors.activation_history = [history_endorsement]
        endorsement.contract_endorsements = endorsement.contract_endorsements

    @classmethod
    def renew_contracts(cls, contracts):
        pool = Pool()
        Endorsement = pool.get('endorsement')
        ContractEndorsement = pool.get('endorsement.contract')
        Definition = pool.get('endorsement.definition')
        renewal_definition, = Definition.search([('code', '=',
                    'renew_contract')])
        endorsements = [Endorsement(
                definition=renewal_definition,
                effective_date=x.end_date + relativedelta(days=1),
                contract_endorsements=[ContractEndorsement(contract=x,
                        activation_history=[])])
            for x in contracts]
        for endorsement in endorsements:
            cls.add_renewal_endorsement(endorsement)
        Endorsement.save(endorsements)
        return endorsements

    @classmethod
    def state_view_name(cls):
        return 'endorsement_renewal.endorsement_contract_renewal_view_form'


class StartEndorsement:
    __metaclass__ = PoolMeta
    __name__ = 'endorsement.start'


add_endorsement_step(StartEndorsement, ContractRenew, 'renew_contract')

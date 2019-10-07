# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from dateutil.relativedelta import relativedelta

from trytond.pool import PoolMeta, Pool

from trytond.modules.coog_core import fields
from trytond.modules.coog_core.api import CODED_OBJECT_SCHEMA
from trytond.modules.bank_cog.api import BANK_ACCOUNT_REFERENCE

from trytond.modules.endorsement.wizard import EndorsementWizardStepMixin


__all__ = [
    'APIConfiguration',
    'APIEndorsement',
    'APIClaimEndorsement',
    ]


class APIConfiguration(metaclass=PoolMeta):
    __name__ = 'api.configuration'

    change_bank_account_definition = fields.Many2One(
        'endorsement.definition', 'Change Bank Account Definition',
        domain=[
            ('ordered_endorsement_parts.endorsement_part.view', '=',
                'change_direct_debit_account')],
        ondelete='RESTRICT',
        help='The endorsement definition that will be bound to endorsements '
        'generated from the change_direct_debit_account API')


class APIEndorsement(metaclass=PoolMeta):
    __name__ = 'api.endorsement'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._apis.update({
                'change_bank_account': {
                    'description': 'Changes the direct debit account used to '
                    'pay one or more contracts',
                    'readonly': False,
                    'public': False,
                    },
                })

    @classmethod
    def change_bank_account(cls, parameters):
        pool = Pool()
        Endorsement = pool.get('endorsement')

        endorsement = Endorsement()
        endorsement.definition = parameters['endorsement_definition']
        endorsement.effective_date = parameters['date']

        cls._change_bank_account_update_party(endorsement, parameters)
        cls._change_bank_account_update_contracts(endorsement, parameters)

        result = cls._complete_endorsement(
             endorsement, parameters.get('options', {}))
        return result

    @classmethod
    def _change_bank_account_update_party(cls, endorsement, parameters):
        pool = Pool()
        PartyAPI = pool.get('api.party')

        new_accounts_per_number = {}
        for account_data in parameters['new_accounts']:
            new_account = PartyAPI._new_bank_account(account_data)
            new_account.start_date = parameters['date']
            new_account.save()
            new_accounts_per_number[account_data['number']] = new_account

        parameters['_new_accounts'] = new_accounts_per_number

        updates = {}
        for change in parameters.get('direct_debit_changes', []):
            if 'account' not in change['new_account']:
                # The new account referenced a newly created account
                change['new_account']['account'] = new_accounts_per_number[
                    change['new_account']['number']]
            updates[change['previous_account']['account'].id] = change[
                'new_account']['account'].id

        # Should we actually do this ?
        for account in parameters['party'].bank_accounts:
            if account.id in updates and (not account.end_date or
                    account.end_date > parameters['date']):
                account.end_date = parameters['date'] - relativedelta(days=1)

        parameters['party'].bank_accounts += tuple(
            new_accounts_per_number.values())
        parameters['party'].save()

    @classmethod
    def _change_bank_account_update_contracts(cls, endorsement, parameters):
        if 'direct_debit_changes' not in parameters:
            return

        pool = Pool()
        Contract = pool.get('contract')
        ContractEndorsement = pool.get('endorsement.contract')

        possible_contracts = Contract.search([
                ('billing_informations.payer', '=', parameters['party'])])

        contract_endorsements = []
        for contract in possible_contracts:
            billing_info = contract._billing_information_at_date(
                parameters['date'])

            match = cls._change_bank_account_must_update_contract(billing_info,
                contract, parameters)
            if match is None:
                continue
            cls._change_bank_account_update_contract(billing_info, contract,
                match, parameters)
            contract.billing_informations = list(contract.billing_informations)

            contract_endorsement = ContractEndorsement()
            contract_endorsement.contract = contract
            EndorsementWizardStepMixin._update_endorsement(
                contract_endorsement, contract._save_values)

            if not contract_endorsement.clean_up():
                contract_endorsements.append(contract_endorsement)

        endorsement.contract_endorsements = contract_endorsements

    @classmethod
    def _change_bank_account_must_update_contract(cls, billing_info,
            contract, parameters):
        if not billing_info or not billing_info.direct_debit:
            return None
        if billing_info.payer != parameters['party']:
            return None

        for change in parameters['direct_debit_changes']:
            if (change['previous_account']['account'] ==
                    billing_info.direct_debit_account):
                return change

    @classmethod
    def _change_bank_account_update_contract(cls, billing_information,
            contract, match, parameters):
        if parameters['date'] != (
                billing_information.date or contract.initial_start_date):
            billing_information = cls._new_billing_information(contract,
                billing_information)
            billing_information.date = parameters['date']
        billing_information.direct_debit_account = match['new_account'][
            'account']
        return billing_information

    @classmethod
    def _new_billing_information(cls, contract, from_billing_info):
        new_billing_info = Pool().get('contract.billing_information')()
        cls._init_billing_information(new_billing_info, from_billing_info)
        contract.billing_informations += (new_billing_info,)
        return new_billing_info

    @classmethod
    def _init_billing_information(cls, new_billing_info, from_billing_info):
        new_billing_info.payer = from_billing_info.payer
        new_billing_info.billing_mode = from_billing_info.billing_mode
        new_billing_info.payment_term = from_billing_info.payment_term
        new_billing_info.direct_debit_day = from_billing_info.direct_debit_day

    @classmethod
    def _change_bank_account_schema(cls):
        PartyAPI = Pool().get('api.party')

        schema = cls._endorsement_base_schema()
        schema['properties'].update({
                'party': CODED_OBJECT_SCHEMA,
                'new_accounts': {
                    'type': 'array',
                    'minItems': 1,
                    'additionalItems': False,
                    'items': PartyAPI._party_bank_account_schema(),
                    },
                'direct_debit_changes':
                cls._change_bank_account_direct_debit_change_schema(),
                })
        schema['required'] = ['party', 'new_accounts']
        return schema

    @classmethod
    def _change_bank_account_direct_debit_change_schema(cls):
        return {
            'type': 'array',
            'additionalItems': False,
            'items': {
                'type': 'object',
                'additionalProperties': False,
                'required': ['new_account', 'previous_account'],
                'properties': {
                    'new_account': BANK_ACCOUNT_REFERENCE,
                    'previous_account': BANK_ACCOUNT_REFERENCE,
                    },
                },
            }

    @classmethod
    def _change_bank_account_output_schema(cls):
        return cls._endorsement_base_output_schema()

    @classmethod
    def _change_bank_account_convert_input(cls, parameters):
        pool = Pool()
        API = pool.get('api')
        PartyAPI = pool.get('api.party')

        parameters = cls._endorsement_base_convert_input(
            'change_bank_account', parameters)
        parameters['party'] = API.instantiate_code_object('party.party',
            parameters['party'])

        for account_data in parameters['new_accounts']:
            PartyAPI._party_bank_account_convert(account_data, None, None)

        if 'direct_debit_changes' in parameters:
            for changes in parameters['direct_debit_changes']:
                cls._change_bank_account_direct_debit_convert_input(changes,
                    parameters)

        return parameters

    @classmethod
    def _change_bank_account_direct_debit_convert_input(cls, changes,
            parameters):
        pool = Pool()
        API = pool.get('api')
        PartyAPI = pool.get('api.party')

        # Look for an existing account on the party matching the given
        # previous account
        changes['previous_account']['account'] = \
            PartyAPI._find_party_bank_account(parameters['party'],
                changes['previous_account'])
        if not changes['previous_account']['account']:
            API.add_input_error({
                    'type': 'previous_bank_account_not_found',
                    'data': {
                        'party': parameters['party'].code,
                        },
                    })

        # Check that the 'new_account' is either one of the newly
        # created accounts, or an existing account on the party
        if 'number' in changes['new_account']:
            if changes['new_account']['number'] in [
                    x.get('number', None)
                    for x in parameters['new_accounts']]:
                return

        changes['new_account']['account'] = \
            PartyAPI._find_party_bank_account(parameters['party'],
                changes['new_account'])
        if not changes['new_account']['account']:
            API.add_input_error({
                    'type': 'new_bank_account_not_found',
                    'data': {
                        'party': parameters['party'].code,
                        },
                    })

    @classmethod
    def _change_bank_account_examples(cls):
        return [
            {
                'input': {
                    'party': {
                        'code': '1234',
                        },
                    'date': '2020-05-12',
                    'new_accounts': [
                        {
                            'number': 'FR7615970003860000690570007',
                            'bank': {'bic': 'ABCDEFGHXXX'},
                            },
                        ],
                    'direct_debit_changes': [
                        {
                            'previous_account': {
                                'number': 'FR7619530001040006462803348',
                                },
                            'new_account': {
                                'number': 'FR7615970003860000690570007',
                                },
                            },
                        ],
                    },
                'output': {
                    'endorsements': [
                        {
                            'id': 4123,
                            'number': '1412398',
                            'state': 'applied',
                            'definition': 'change_direct_debit_account',
                            },
                        ],
                    },
                },
            ]


class APIClaimEndorsement(metaclass=PoolMeta):
    __name__ = 'api.endorsement'

    @classmethod
    def _change_bank_account_update_party(cls, endorsement, parameters):
        super()._change_bank_account_update_party(endorsement, parameters)

        if 'new_claim_account' not in parameters:
            return

        if 'account' in parameters['new_claim_account']:
            parameters['party'].forced_claim_bank_account = parameters[
                'new_claim_account']['account']
        else:
            parameters['party'].forced_claim_bank_account = parameters[
                '_new_accounts'][parameters['new_claim_account']['number']]

        parameters['party'].save()

    @classmethod
    def _change_bank_account_schema(cls):
        schema = super()._change_bank_account_schema()

        schema['properties']['new_claim_account'] = BANK_ACCOUNT_REFERENCE
        return schema

    @classmethod
    def _change_bank_account_convert_input(cls, parameters):
        pool = Pool()
        API = pool.get('api')
        PartyAPI = pool.get('api.party')

        parameters = super()._change_bank_account_convert_input(parameters)

        if 'new_claim_account' not in parameters:
            return parameters

        # Check that the 'claim_account' is either one of the newly
        # created accounts, or an existing account on the party
        if 'number' in parameters['new_claim_account']:
            if parameters['new_claim_account']['number'] in [
                    x.get('number', None)
                    for x in parameters['new_accounts']]:
                return parameters

        parameters['new_claim_account']['account'] = \
            PartyAPI._find_party_bank_account(parameters['party'],
                parameters['new_claim_account'])
        if not parameters['new_claim_account']['account']:
            API.add_input_error({
                    'type': 'new_claim_bank_account_not_found',
                    'data': {
                        'party': parameters['party'].code,
                        },
                    })

        return parameters

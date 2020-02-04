# This file is part of Cojg. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool

from trytond.modules.coog_core import utils

from trytond.modules.api import DATE_SCHEMA, POSITIVE_AMOUNT_SCHEMA, RATE_SCHEMA
from trytond.modules.api import date_from_api, amount_from_api, date_for_api
from trytond.modules.coog_core.api import CODED_OBJECT_SCHEMA
from trytond.modules.contract.api import CONTRACT_SCHEMA


__all__ = [
    'ContractAPI',
    ]


class ContractAPI(metaclass=PoolMeta):
    __name__ = 'api.contract'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._apis.update({
                'update_underwriting': {
                    'description': 'Update underwriting decision for a '
                    'contract',
                    'public': False,
                    'readonly': False,
                    },
                'set_underwriting_subscriber_decision': {
                    'description': 'Update subscriber decision for a '
                    'contract\'s underwriting',
                    'public': False,
                    'readonly': False,
                    },
                })

    @classmethod
    def _subscribe_contracts_execute_methods(cls, options):
        result = super()._subscribe_contracts_execute_methods(options)
        if options.get('update_underwritings', True):
            result.append(
                {
                    'priority': 80,
                    'name': 'update_underwritings',
                    'params': None,
                    'error_type': 'failed_underwriting_initialization',
                    },
                )
        return result

    @classmethod
    def _simulate_default_options(cls):
        options = super()._simulate_default_options()
        options.update({
                'update_underwritings': False,
                })
        return options

    @classmethod
    def _validate_contract_input(cls, data):
        # temporarily add contract_underwriting keys which are not supposed to
        # be here (wrong business kind) but that validate requires anyway
        ExtraData = Pool().get('extra_data')
        extra = data['extra_data']
        recomputed = data['product'].refresh_extra_data(extra.copy())
        temp_keys = [key for key in set(recomputed) - set(extra)
            if ExtraData._extra_data_struct(key)['kind'] ==
            'contract_underwriting']
        for key in temp_keys:
            extra[key] = recomputed[key]
        super(ContractAPI, cls)._validate_contract_input(data)
        for key in temp_keys:
            del extra[key]

    @classmethod
    def _validate_contract_option_input(cls, data):
        # temporarily add option_underwriting keys which are not supposed to be
        # here (wrong business kind) but that validate requires anyway
        ExtraData = Pool().get('extra_data')
        extra = data['extra_data']
        recomputed = data['coverage'].refresh_extra_data(extra.copy())
        temp_keys = [key for key in set(recomputed) - set(extra)
            if ExtraData._extra_data_struct(key)['kind'] ==
            'option_underwriting']
        for key in temp_keys:
            extra[key] = recomputed[key]
        super(ContractAPI, cls)._validate_contract_option_input(data)
        for key in temp_keys:
            del extra[key]

    @classmethod
    def update_underwriting(cls, parameters):

        cls._update_underwriting_contract(parameters)

        contract = parameters['contract']
        contract.underwritings = list(contract.underwritings)
        contract.covered_elements = list(contract.covered_elements)
        for covered_element in contract.covered_elements:
            covered_element.options = list(covered_element.options)
        contract.options = list(contract.options)
        contract.save()

        # Maybe we should also try to activate / re-compute things here?
        contract.decline_options_after_underwriting()
        contract.do_calculate()

    @classmethod
    def _update_underwriting_contract(cls, parameters):
        pool = Pool()
        API = pool.get('api')
        ContractUnderwriting = pool.get('contract.underwriting')

        underwriting = parameters['underwriting']
        underwriting.decision_date = parameters['decision_date']

        for option_data in parameters['options']:
            cls._update_underwriting_option_data(option_data)

        possible_decisions = ContractUnderwriting.get_possible_decisions(
            underwriting.underwriting_options)
        if parameters['decision'] not in possible_decisions:
            API.add_input_error({
                    'type': 'unauthorized_contract_underwriting_decision',
                    'data': {
                        'contract': parameters['contract'].rec_name,
                        'decision': parameters['decision'].code,
                        'allowed_decisions': sorted(
                            x.code for x in possible_decisions),
                        },
                    })
        underwriting.decision = parameters['decision']
        underwriting.underwriting_options = list(
            underwriting.underwriting_options)

    @classmethod
    def _update_underwriting_option_data(cls, option_data):
        option_data['underwriting'].decision = option_data['decision']

        cls._update_underwriting_option_exclusions(option_data)
        cls._update_underwriting_option_extra_premiums(option_data)

    @classmethod
    def _update_underwriting_option_exclusions(cls, option_data):
        # For now, we remove nothing, we only update / add

        Exclusion = Pool().get('contract.option.exclusion')
        existing_exclusions = {x.exclusion.code: x
            for x in option_data['option'].exclusions}

        exclusions = list(option_data['option'].exclusions)
        for exclusion_data in option_data['exclusions']:
            if exclusion_data['type'].code in existing_exclusions:
                exclusion = existing_exclusions[exclusion_data['type'].code]
            else:
                exclusion = Exclusion()
                exclusion.exclusion = exclusion_data['type']
                exclusions.append(exclusion)
            exclusion.comment = exclusion_data.get('custom_content', '')
        option_data['option'].exclusions = exclusions

    @classmethod
    def _update_underwriting_option_extra_premiums(cls, option_data):
        # For now, we remove nothing, we only update / add

        ExtraPremium = Pool().get('contract.option.extra_premium')
        existing_extra_premiums = {x.motive.code: x
            for x in option_data['option'].extra_premiums}

        extra_premiums = list(option_data['option'].extra_premiums)
        for extra_premium_data in option_data['extra_premiums']:
            if extra_premium_data['type'].code in existing_extra_premiums:
                extra_premium = existing_extra_premiums[
                    extra_premium_data['type'].code]
            else:
                extra_premium = ExtraPremium()
                extra_premium.motive = extra_premium_data['type']
                extra_premiums.append(extra_premium)
            cls._update_underwriting_option_extra_premium(extra_premium,
                extra_premium_data)
        option_data['option'].extra_premiums = extra_premiums

    @classmethod
    def _update_underwriting_option_extra_premium(cls, extra_premium, data):
        extra_premium.calculation_kind = data['mode']
        extra_premium.rate = data.get('rate', None)
        extra_premium.flat_amount = data.get('flat_amount', None)
        extra_premium.manual_end_date = data.get('end', None)

    @classmethod
    def _update_underwriting_schema(cls):
        return {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'contract': CONTRACT_SCHEMA,
                'decision': CODED_OBJECT_SCHEMA,
                'decision_date': DATE_SCHEMA,
                'options': {
                    'type': 'array',
                    'additionalItems': False,
                    'minItems': 1,
                    'items': cls._update_underwriting_option_schema(),
                    },
                },
            'required': ['contract', 'decision', 'options'],
            }

    @classmethod
    def _update_underwriting_option_schema(cls):
        return {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'coverage': CODED_OBJECT_SCHEMA,
                'party': CODED_OBJECT_SCHEMA,
                'decision': CODED_OBJECT_SCHEMA,
                'exclusions': {
                    'type': 'array',
                    'additionalItems': False,
                    'minItems': 1,
                    'items': cls._update_underwriting_exclusion_schema(),
                    },
                'extra_premiums': {
                    'type': 'array',
                    'additionalItems': False,
                    'minItems': 1,
                    'items': cls._update_underwriting_extra_premium_schema(),
                    },
                },
            # Party is required since underwriting is usually not required for
            # non person insurance. Also, that's the sole user friendly way we
            # have to properly identify a covered element
            'required': ['party', 'coverage', 'decision'],
            }

    @classmethod
    def _update_underwriting_exclusion_schema(cls):
        return {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'type': CODED_OBJECT_SCHEMA,
                'custom_content': {'type': 'string'},
                },
            'required': ['type'],
            }

    @classmethod
    def _update_underwriting_extra_premium_schema(cls):
        return {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'type': CODED_OBJECT_SCHEMA,
                'mode': {
                    'type': 'string',
                    'enum': ['flat', 'rate'],
                    },
                'flat_amount': POSITIVE_AMOUNT_SCHEMA,
                'rate': RATE_SCHEMA,
                'end': DATE_SCHEMA,
                },
            'required': ['type', 'mode'],
            'oneOf': [
                {
                    'properties': {
                        'mode': 'flat',
                        'flat_amount': POSITIVE_AMOUNT_SCHEMA,
                        },
                    'required': ['mode', 'flat_amount'],
                    },
                {
                    'properties': {
                        'mode': 'rate',
                        'rate': RATE_SCHEMA,
                        },
                    'required': ['mode', 'rate'],
                    },
                ],
            }

    @classmethod
    def _update_underwriting_convert_input(cls, parameters):
        pool = Pool()
        API = pool.get('api')

        parameters['contract'] = cls._get_contract(parameters['contract'])
        parameters['decision'] = API.instantiate_code_object(
            'underwriting.decision', parameters['decision'])

        if 'decision_date' in parameters:
            parameters['decision_date'] = date_from_api(
                parameters['decision_date'])
        else:
            parameters['decision_date'] = utils.today()

        if parameters['decision_date'] > utils.today():
            API.add_input_error({
                    'type': 'future_decision_date',
                    'data': {
                        'decision_date': date_for_api(
                            parameters['decision_date']),
                        },
                    })

        for option_data in parameters.get('options', []):
            cls._update_underwriting_convert_option_input(option_data,
                parameters['contract'])

        try:
            parameters['underwriting'] = parameters[
                'contract'].underwritings[-1]
        except Exception:
            API.add_input_error({
                    'type': 'contract_without_underwriting',
                    'data': {
                        'contract': parameters['contract'].rec_name,
                        },
                    })
        return parameters

    @classmethod
    def _update_underwriting_convert_option_input(cls, option_data, contract):
        pool = Pool()
        API = pool.get('api')

        option_data['coverage'] = API.instantiate_code_object(
            'offered.option.description', option_data['coverage'])
        option_data['decision'] = API.instantiate_code_object(
            'underwriting.decision', option_data['decision'])
        option_data['party'] = API.instantiate_code_object(
            'party.party', option_data['party'])

        option_data['exclusions'] = option_data.get('exclusions', [])
        for exclusion_data in option_data['exclusions']:
            exclusion_data['type'] = API.instantiate_code_object(
                'offered.exclusion', exclusion_data['type'])

        option_data['extra_premiums'] = option_data.get('extra_premiums', [])
        for extra_premium_data in option_data['extra_premiums']:
            extra_premium_data['type'] = API.instantiate_code_object(
                'extra_premium.kind', extra_premium_data['type'])
            if 'rate' in extra_premium_data:
                extra_premium_data['rate'] = amount_from_api(
                    extra_premium_data['rate'])
            if 'flat_amount' in extra_premium_data:
                extra_premium_data['flat_amount'] = amount_from_api(
                    extra_premium_data['flat_amount'])
            if 'end' in extra_premium_data:
                extra_premium_data['end'] = date_from_api(
                    extra_premium_data['end'])

        option_data['option'] = cls._get_option(contract, option_data)

        try:
            option_data['underwriting'] = \
                contract.underwritings[-1]._underwriting_for_option(
                    option_data['option'])
        except Exception:
            API.add_input_error({
                    'type': 'option_without_underwriting',
                    'data': {
                        'contract': contract.rec_name,
                        'option': option_data['option'].rec_name,
                        },
                    })
        if option_data['underwriting'].decision:
            # Is this actually right ?
            API.add_input_error({
                    'type': 'underwriting_decision_already_set',
                    'data': {
                        'option': option_data['option'].rec_name,
                        'new_decision': option_data['decision'].code,
                        'existing_decision':
                        option_data['underwriting'].decision.code,
                        },
                    })

    @classmethod
    def _update_underwriting_validate_input(cls, parameters):
        API = Pool().get('api')

        # Check option decisions, to be sure
        for option_data in parameters['options']:
            cls._update_underwriting_validate_option(option_data,
                parameters['contract'])

        missing_underwritings = (
            {x.option
                for x in parameters['underwriting'].underwriting_options
                if x.decision is None} -
            {x['option'] for x in parameters['options']})
        if missing_underwritings:
            API.add_input_error({
                    'type': 'incomplete_underwriting',
                    'data': {
                        'missing_options': sorted(
                            x.rec_name for x in missing_underwritings),
                        },
                    })

        # Contract decision consistency cannot be checked cleanly because it is
        # based on the option values. So it will be checked later on, when
        # doing the actual modification
        return parameters

    @classmethod
    def _update_underwriting_validate_option(cls, option_data, contract):
        pool = Pool()
        API = pool.get('api')

        option = option_data['option']
        if (option_data['decision'] not in
                option_data['underwriting'].possible_decisions):
            API.add_input_error({
                    'type': 'unauthorized_underwriting_decision',
                    'data': {
                        'contract': contract.rec_name,
                        'option': option.rec_name,
                        'decision': option_data['decision'].code,
                        'allowed_decisions': sorted(x.code for x in
                            option_data['underwriting'].possible_decisions),
                        },
                    })

        if (option_data['exclusions'] and
                not option.coverage.with_exclusions):
            API.add_input_error({
                    'type': 'coverage_without_exclusions',
                    'data': {
                        'coverage': option.coverage.code,
                        },
                    })

        if (option_data['extra_premiums'] and
                not option.coverage.with_extra_premiums):
            API.add_input_error({
                    'type': 'coverage_without_extra_premiums',
                    'data': {
                        'coverage': option.coverage.code,
                        },
                    })

    @classmethod
    def _update_underwriting_examples(cls):
        return [
            {
                'input': {
                    'contract': {'number': '1234567890'},
                    'decision': {'code': 'accepted_with_conditions'},
                    'decision_date': '2020-04-06',
                    'options': [
                        {
                            'coverage': {'code': 'ALP'},
                            'party': {'code': '153242'},
                            'decision': {'code': 'accepted'},
                            },
                        {
                            'coverage': {'code': 'BET'},
                            'party': {'code': '153242'},
                            'decision': {'code': 'accepted_with_conditions'},
                            'exclusions': [
                                {
                                    'type': {'code': 'cardiac_arrest'},
                                    },
                                {
                                    'type': {'code': 'lung_cancer'},
                                    'custom_content': 'Very heavy smoker',
                                    },
                                ],
                            'extra_premiums': [
                                {
                                    'type': {'code': 'medical'},
                                    'mode': 'rate',
                                    'rate': '0.50',
                                    },
                                {
                                    'type': {'code': 'medical'},
                                    'mode': 'flat',
                                    'flat_amount': '0.50',
                                    },
                                ],
                            },
                        ],
                    },
                'output': None,
                },
            ]

    """ ↓↓↓↓ Start Subscriber Decision API Methods ↓↓↓↓ """

    @classmethod
    def set_underwriting_subscriber_decision(cls, parameters):
        underwriting = parameters['underwriting']
        underwriting.subscriber_decision = parameters['subscriber_decision']
        underwriting.subscriber_decision_date = parameters['decision_date']
        underwriting.save()

    @classmethod
    def _set_underwriting_subscriber_decision_schema(cls):
        return {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'contract': CONTRACT_SCHEMA,
                'subscriber_decision': {
                    'type': 'string',
                    'enum': ['accepted', 'refused']
                    },
                'decision_date': DATE_SCHEMA,
                },
            'required': ['contract', 'subscriber_decision'],
            }

    @classmethod
    def _set_underwriting_subscriber_decision_examples(cls):
        return [
            {
                'input': {
                    'contract': {'number': '1234567890'},
                    'subscriber_decision': 'accepted',
                    'decision_date': '2020-04-06',
                    },
                'output': None,
                }
            ]

    @classmethod
    def _set_underwriting_subscriber_decision_convert_input(cls, parameters):
        pool = Pool()
        API = pool.get('api')
        contract = cls._get_contract(parameters['contract'])
        parameters['contract'] = contract
        if not contract.underwritings:
            API.add_input_error({
                    'type': 'no_underwriting_on_contract',
                    'data': {
                        'contract': contract.rec_name
                        },
                    })

        parameters['underwriting'] = contract.underwritings[-1]

        if 'decision_date' in parameters:
            parameters['decision_date'] = date_from_api(
                parameters['decision_date'])
        else:
            parameters['decision_date'] = utils.today()

        if parameters['decision_date'] > utils.today():
            API.add_input_error({
                    'type': 'future_decision_date',
                    'data': {
                        'decision_date': date_for_api(
                            parameters['decision_date']),
                        },
                    })
        parameters['decision_date'] = parameters['decision_date']
        return parameters

    """ *** End Subscriber Decision API Methods *** """

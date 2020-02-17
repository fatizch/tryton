# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms
import copy

from trytond.pool import PoolMeta, Pool

from trytond.modules.api import date_from_api
from trytond.modules.api import DATE_SCHEMA
from trytond.modules.api import AMOUNT_SCHEMA, amount_for_api, amount_from_api

from trytond.modules.coog_core import utils
from trytond.modules.coog_core.api import CODED_OBJECT_SCHEMA, OBJECT_ID_SCHEMA


__all__ = [
    'APIProduct',
    'APIContract',
    'APICore',
    ]


class APIProduct(metaclass=PoolMeta):
    __name__ = 'api.product'

    @classmethod
    def _describe_product(cls, product):
        pool = Pool()
        Agent = pool.get('commission.agent')

        result = super()._describe_product(product)

        agent_parameters = cls._describe_product_find_agents_parameters(product)
        if agent_parameters:
            agents = Agent.find_agents(**agent_parameters)
            if agents:
                result['commission_agents'] = [
                    cls._describe_agent(agent) for agent in agents]
        return result

    @classmethod
    def _describe_product_find_agents_parameters(cls, product):
        pool = Pool()
        Core = pool.get('api.core')

        network = Core._get_dist_network()
        if network is None:
            return {}
        return {
            'products': [product],
            'dist_network': network,
            'type_': 'agent',
            }

    @classmethod
    def _describe_agent(cls, agent):
        values = {
            'id': agent.id,
            'code': agent.code,
            'plan': agent.plan.code,
            }
        if agent.per_contract_rate_override:
            values['default_rate'] = amount_for_api(agent.rate_default * 100)
            values['minimum_rate'] = amount_for_api(agent.rate_minimum * 100)
            values['maximum_rate'] = amount_for_api(agent.rate_maximum * 100)
        return values

    @classmethod
    def _describe_product_schema(cls):
        schema = super()._describe_product_schema()
        schema['properties']['commission_agents'] = {
            'type': 'array',
            'additionalItems': False,
            'items': cls._describe_agent_schema(),
            }
        return schema

    @classmethod
    def _describe_agent_schema(cls):
        return {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'id': OBJECT_ID_SCHEMA,
                'code': {'type': 'string'},
                'plan': {'type': 'string'},
                'default_rate': AMOUNT_SCHEMA,
                'minimum_rate': AMOUNT_SCHEMA,
                'maximum_rate': AMOUNT_SCHEMA,
                },
            'required': ['id', 'code', 'plan'],
            }

    @classmethod
    def _describe_products_examples(cls):
        examples = super()._describe_products_examples()
        examples[-1]['output'][-1]['commission_agents'] = [
            {
                'id': 1,
                'code': 'agent_1',
                'plan': 'plan_10_percents',
                },
            {
                'id': 2,
                'code': 'agent_2',
                'plan': 'plan_flexible',
                'default_rate': '15',
                'minimum_rate': '10',
                'maximum_rate': '30',
                },
            ]
        return examples


class APIContract(metaclass=PoolMeta):
    __name__ = 'api.contract'

    @classmethod
    def _create_contract(cls, contract_data, created):
        contract = super()._create_contract(contract_data, created)

        if contract_data['agent']:
            contract.agent = contract_data['agent']
            if 'agent_rate' in contract_data:
                contract.commission_rate_overrides = [
                    {'agent': contract.agent.id,
                        'custom_rate': contract_data['agent_rate']},
                    ]
        return contract

    @classmethod
    def _contract_convert(cls, data, options, parameters, minimum=False):
        super()._contract_convert(data, options, parameters, minimum=minimum)
        cls._contract_convert_commission_data(data, options, parameters,
            minimum=minimum)

    @classmethod
    def _contract_convert_commission_data(cls, data, options, parameters,
            minimum=False):
        pool = Pool()
        API = pool.get('api')

        if minimum is False or 'agent' in data:
            data['agent'] = API.instantiate_code_object('commission.agent',
                data['agent'])
        else:
            data['agent'] = None

        if data['agent'] and data['agent'].per_contract_rate_override:
            if 'agent_rate' in data:
                data['agent_rate'] = amount_from_api(data['agent_rate']) / 100
                if (data['agent_rate'] > data['agent'].rate_maximum or
                        data['agent_rate'] < data['agent'].rate_minimum):
                    API.add_input_error({
                            'type': 'invalid_custom_rate',
                            'data': {
                                'value': amount_for_api(
                                    data['agent_rate'] * 100),
                                'minimum': amount_for_api(
                                    data['agent'].rate_minimum * 100),
                                'maximum': amount_for_api(
                                    data['agent'].rate_maximum * 100),
                                }
                            })
        elif 'agent_rate' in data:
            API.add_input_error({
                    'type': 'unauthorized_commission_rate_modification',
                    'data': {},
                    })

    @classmethod
    def _validate_contract_input(cls, data):
        super()._validate_contract_input(data)
        if not data['agent']:
            return
        pool = Pool()
        API = pool.get('api')
        Agent = pool.get('commission.agent')

        network = data['dist_network']
        agent = data['agent']

        agent_parameters = cls._subscribe_contracts_find_agents_parameters(data)
        possible_agents = Agent.find_agents(**agent_parameters)
        if agent.id not in [x.id for x in possible_agents]:
            API.add_input_error({
                    'type': 'unauthorized_agent',
                    'data': {
                        'product': data['product'].code,
                        'dist_network': network.id,
                        'agent': data['agent'].code,
                        },
                    })

    @classmethod
    def _subscribe_contracts_find_agents_parameters(cls, contract_data):
        return {
            'products': [contract_data['product']],
            'dist_network': contract_data['dist_network'],
            'type_': 'agent',
            }

    @classmethod
    def _contract_schema(cls, minimum=False):
        schema = super()._contract_schema(minimum=minimum)
        schema['properties']['agent'] = CODED_OBJECT_SCHEMA
        schema['properties']['agent_rate'] = AMOUNT_SCHEMA
        if not minimum:
            schema['required'].append('agent')
        return schema

    @classmethod
    def _subscribe_contracts_examples(cls):
        examples = super()._subscribe_contracts_examples()
        for example in examples:
            for contract_data in example['input']['contracts']:
                contract_data['agent'] = {'code': 'agent_007'}
        examples[-1]['input']['contracts'][-1]['agent_rate'] = '20.00'
        return examples

    @classmethod
    def _compute_billing_modes_examples(cls):
        examples = super()._compute_billing_modes_examples()
        for example in examples:
            for contract_data in example['input']['contracts']:
                contract_data['agent'] = {'code': 'agent_007'}
        return examples

    @classmethod
    def _simulate_examples(cls):
        examples = super()._simulate_examples()
        for example in examples:
            for contract_data in example['input']['contracts']:
                contract_data['agent'] = {'code': 'agent_007'}
        return examples


class APICore(metaclass=PoolMeta):
    __name__ = 'api.core'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._apis.update({
                'close_distribution_network': {
                    'description': 'Set end date to the specified date '
                    'or today and block payments',
                    'public': False,
                    'readonly': False,
                    },
                'reopen_distribution_network': {
                    'description': 'Remove the end date and unblock '
                    'payments',
                    'public': False,
                    'readonly': False,
                    },
                })

    @classmethod
    def close_distribution_network(cls, parameters):
        pool = Pool()
        Party = pool.get('party.party')

        parties = []
        for network_data in parameters:
            cls._close_distribution_network_block_payments(network_data)
            cls._close_distribution_network_end_agents(network_data)
            network_data['network'].party.agents = list(
                network_data['network'].party.agents)
            parties.append(network_data['network'].party)
        Party.save(parties)
        return

    @classmethod
    def _close_distribution_network_block_payments(cls, data):
        if 'block_payments' in data and (
                data['network'].party.block_payable_payments !=
                data['block_payments']):
            data['network'].party.block_payable_payments = \
                data['block_payments']

    @classmethod
    def _close_distribution_network_end_agents(cls, data):
        for agent in data['network'].party.agents:
            agent.end_date = data['end_date']

    @classmethod
    def _close_distribution_network_schema(cls):
        return {
            'type': 'array',
            'additionalItems': False,
            'items': cls._close_distribution_network_schema_item(),
            'minItems': 1,
            }

    @classmethod
    def _close_distribution_network_schema_item(cls):
        code_req = cls._close_distribution_network_schema_shared()
        id_req = copy.deepcopy(code_req)
        code_req['properties']['code'] = {'type': 'string'}
        code_req['required'] = ['code']
        id_req['properties']['id'] = {'type': 'boolean'}
        id_req['required'] = ['id']
        return {'oneOf': [code_req, id_req]}

    @classmethod
    def _close_distribution_network_schema_shared(cls):
        return {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'end_date': DATE_SCHEMA,
                'block_payments': {'type': 'boolean'},
                },
            }

    @classmethod
    def _close_distribution_network_examples(cls):
        return [
            {
                'input': [
                    {
                        'code': 'C1',
                        'end_date': '2019-12-31',
                        'block_payments': True
                    },
                ],
                'output': None,
            }
        ]

    @classmethod
    def _close_distribution_network_convert_input(cls, parameters):
        for parameter in parameters:
            cls._close_distribution_network_convert_end_date(parameter)
            cls._close_distribution_network_convert_code(parameter)
        return parameters

    @classmethod
    def _close_distribution_network_convert_end_date(cls, parameter):
        if 'end_date' in parameter:
            parameter['end_date'] = date_from_api(parameter['end_date'])
        else:
            parameter['end_date'] = utils.today()

    @classmethod
    def _close_distribution_network_convert_code(cls, parameter):
        pool = Pool()
        API = pool.get('api')
        if 'code' in parameter:
            parameter['network'] = API.instantiate_code_object(
                'distribution.network',
                {'code': parameter['code']})
        elif 'id' in parameter:
            parameter['network'] = API.instantiate_code_object(
                'distribution.network',
                {'id': parameter['id']})

    @classmethod
    def _close_distribution_network_validate_input(cls, parameters):
        pool = Pool()
        API = pool.get('api')
        for data in parameters:
            if data['network'].party is None:
                API.add_input_error({
                        'type': 'cannot_close_network_wo_party',
                        'data': data['network'].code,
                        })
            else:
                for agent in data['network'].party.agents:
                    if agent.start_date is not None and (
                            data['end_date'] < agent.start_date):
                        API.add_input_error({
                                'type': 'agents_exist_past_close_date',
                                'data': data['network'].code,
                                })
                if all(agent.end_date is not None for agent in
                        data['network'].party.agents):
                    API.add_input_error({
                            'type': 'network_already_closed',
                            'data': data['network'].code,
                            })

    @classmethod
    def reopen_distribution_network(cls, parameters):
        pool = Pool()
        Party = pool.get('party.party')

        parties = []
        for network_data in parameters:
            cls._reopen_party_distribution_network(network_data)
            network_data['network'].party.agents = list(
                network_data['network'].party.agents)
            parties.append(network_data['network'].party)
        Party.save(parties)
        return

    @classmethod
    def _reopen_party_distribution_network(cls, data):
        if data['network'].party.block_payable_payments is not False:
            data['network'].party.block_payable_payments = False
        for agent in data['network'].party.agents:
            agent.end_date = None

    @classmethod
    def _reopen_distribution_network_schema(cls):
        return {
            'type': 'array',
            'additionalItems': False,
            'items': CODED_OBJECT_SCHEMA,
            'minItems': 1
            }

    @classmethod
    def _reopen_distribution_network_examples(cls):
        return [
            {
                'input': [
                    {'code': 'C2'},
                    ],
                'output': None,
            }
        ]

    @classmethod
    def _reopen_distribution_network_convert_input(cls, parameters):
        for parameter in parameters:
            cls._close_distribution_network_convert_code(parameter)
        return parameters

    @classmethod
    def _reopen_distribution_network_validate_input(cls, parameters):
        pool = Pool()
        API = pool.get('api')

        for data in parameters:
            if data['network'].party is None:
                API.add_input_error({
                        'type': 'cannot_reopen_network_wo_party',
                        'data': data['network'].code,
                        })
            else:
                if all(agent.end_date is None for agent in
                        data['network'].party.agents):
                    API.add_input_error({
                        'type': 'network_already_opened',
                        'data': data['network'].code,
                        })

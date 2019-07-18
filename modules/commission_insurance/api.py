# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms
from trytond.pool import PoolMeta, Pool

from trytond.modules.coog_core.api import CODED_OBJECT_SCHEMA, OBJECT_ID_SCHEMA


__all__ = [
    'APIProduct',
    'APIContract',
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
        return {
            'id': agent.id,
            'code': agent.code,
            'plan': agent.plan.code,
            }

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
            ]
        return examples


class APIContract(metaclass=PoolMeta):
    __name__ = 'api.contract'

    @classmethod
    def _create_contract(cls, contract_data, created):
        contract = super()._create_contract(contract_data, created)

        if contract_data['agent']:
            contract.agent = contract_data['agent']

        return contract

    @classmethod
    def _contract_convert(cls, data, options, parameters):
        pool = Pool()
        API = pool.get('api')

        super()._contract_convert(data, options, parameters)

        data['agent'] = API.instantiate_code_object('commission.agent',
            data['agent'])

    @classmethod
    def _validate_contract_input(cls, data):
        pool = Pool()
        API = pool.get('api')
        Agent = pool.get('commission.agent')

        super()._validate_contract_input(data)

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
        schema['required'].append('agent')
        return schema

    @classmethod
    def _subscribe_contracts_examples(cls):
        examples = super()._subscribe_contracts_examples()
        for example in examples:
            for contract_data in example['input']['contracts']:
                contract_data['agent'] = {'code': 'agent_007'}
        return examples

    @classmethod
    def _compute_billing_modes_examples(cls):
        examples = super()._compute_billing_modes_examples()
        for example in examples:
            for contract_data in example['input']['contracts']:
                contract_data['agent'] = {'code': 'agent_007'}
        return examples

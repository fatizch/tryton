# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool

from trytond.modules.coog_core.api import CODED_OBJECT_SCHEMA, OBJECT_ID_SCHEMA
from trytond.modules.coog_core.api import CODED_OBJECT_ARRAY_SCHEMA


__all__ = [
    'APICore',
    'APIProduct',
    'APIContract',
    ]


class APICore(metaclass=PoolMeta):
    __name__ = 'api.core'

    @classmethod
    def _distribution_network_schema(cls):
        schema = super()._distribution_network_schema()
        schema['properties']['commercial_products'] = CODED_OBJECT_ARRAY_SCHEMA
        schema['properties']['is_distributor'] = {
            'type': 'boolean',
            'default': True,
            }
        return schema

    @classmethod
    def _create_distribution_network(cls, network_data):
        network = super()._create_distribution_network(network_data)
        network.commercial_products = network_data.get(
            'commercial_products', [])
        network.is_distributor = network_data['is_distributor']
        return network

    @classmethod
    def _distribution_network_convert(cls, data, parameters):
        API = Pool().get('api')

        super()._distribution_network_convert(data, parameters)
        if 'commercial_products' in data:
            # There should probably be some sort of controls on what products
            # are available here, but nothing exists yet :'(
            data['commercial_products'] = [
                API.instantiate_code_object('distribution.commercial_product',
                    x)
                for x in data['commercial_products']]


class APIProduct(metaclass=PoolMeta):
    __name__ = 'api.product'

    @classmethod
    def describe_products(cls, products):
        results = super().describe_products(products)
        return cls._describe_products_update_commercial_products(results)

    @classmethod
    def _describe_products_update_commercial_products(cls, results):
        pool = Pool()
        Core = pool.get('api.core')

        network = Core._get_dist_network()
        if network is None:
            return results

        new_results = []
        for product_data in results:
            com_products = [x for x in network.all_com_products
                if x.product.id == product_data['id']]
            if com_products:
                product_data['commercial_products'] = [
                    cls._describe_commercial_product(x)
                    for x in com_products]
                new_results.append(product_data)
        return new_results

    @classmethod
    def _describe_commercial_product(cls, commercial_product):
        return {
            'id': commercial_product.id,
            'code': commercial_product.code,
            'name': commercial_product.name,
            }

    @classmethod
    def _describe_product_schema(cls):
        schema = super()._describe_product_schema()
        schema['properties']['commercial_products'] = {
            'type': 'array',
            'additionalItems': False,
            'items': cls._describe_commercial_product_schema(),
            }
        return schema

    @classmethod
    def _describe_commercial_product_schema(cls):
        return {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'id': OBJECT_ID_SCHEMA,
                'code': {'type': 'string'},
                'name': {'type': 'string'},
                },
            'required': ['id', 'code', 'name'],
            }

    @classmethod
    def _describe_products_examples(cls):
        examples = super()._describe_products_examples()
        examples[-1]['output'][-1]['commercial_products'] = [
            {
                'id': 1,
                'code': 'com_product_1',
                'name': 'Commercial Product 1',
                },
            {
                'id': 2,
                'code': 'com_product_2',
                'name': 'Commercial Product 2',
                },
            ]
        return examples


class APIContract(metaclass=PoolMeta):
    __name__ = 'api.contract'

    @classmethod
    def _create_contract(cls, contract_data, created):
        contract = super()._create_contract(contract_data, created)

        # Commercial product is a function field, so we do nothing...
        contract.dist_network = contract_data['dist_network']

        return contract

    @classmethod
    def _contract_convert(cls, data, options, parameters):
        pool = Pool()
        API = pool.get('api')
        Core = pool.get('api.core')

        super()._contract_convert(data, options, parameters)
        network = Core._get_dist_network()

        if network is None:
            API.add_input_error({
                    'type': 'missing_dist_network',
                    'data': {},
                    })
        else:
            data['dist_network'] = network

        data['commercial_product'] = API.instantiate_code_object(
            'distribution.commercial_product', data['commercial_product'])

    @classmethod
    def _validate_contract_input(cls, data):
        pool = Pool()
        API = pool.get('api')

        super()._validate_contract_input(data)

        network = data['dist_network']
        if data['commercial_product'].product != data['product']:
            API.add_input_error({
                    'type': 'inconsistent_commercial_product',
                    'data': {
                        'product': data['product'].code,
                        'com_product': data['commercial_product'].code,
                        },
                    })
        if data['commercial_product'] not in network.all_com_products:
            API.add_input_error({
                    'type': 'unauthorized_commercial_product',
                    'data': {
                        'product': data['product'].code,
                        'commercial_product': data['commercial_product'].code,
                        'dist_network': network.id,
                        },
                    })

    @classmethod
    def _contract_schema(cls, minimum=False):
        schema = super()._contract_schema(minimum=minimum)
        schema['properties']['commercial_product'] = CODED_OBJECT_SCHEMA
        schema['required'].append('commercial_product')
        return schema

    @classmethod
    def _subscribe_contracts_examples(cls):
        examples = super()._subscribe_contracts_examples()
        for example in examples:
            for idx, contract_data in enumerate(example['input']['contracts']):
                contract_data['commercial_product'] = {
                    'code': 'com_product_%i' % idx}
        return examples

    @classmethod
    def _compute_billing_modes_examples(cls):
        examples = super()._compute_billing_modes_examples()
        for example in examples:
            for idx, contract_data in enumerate(example['input']['contracts']):
                contract_data['commercial_product'] = {
                    'code': 'com_product_%i' % idx}
        return examples


class APIParty(metaclass=PoolMeta):
    __name__ = 'api.party'

    @classmethod
    def get_product_name(cls, contract):
        if contract.com_product:
            return contract.com_product.name
        return super().get_product_name(contract)

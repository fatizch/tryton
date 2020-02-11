# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict
from trytond.pool import PoolMeta, Pool

from trytond.modules.coog_core.api import CODED_OBJECT_SCHEMA, OBJECT_ID_SCHEMA
from trytond.modules.coog_core.api import CODED_OBJECT_ARRAY_SCHEMA, CODE_SCHEMA
from trytond.modules.web_configuration.resource import WebUIResourceMixin
from trytond.modules.api import DATE_SCHEMA
from trytond.modules.api import api_context


__all__ = [
    'APIIdentity',
    'APICore',
    'APIProduct',
    'APIContract',
    ]


class APIIdentity(metaclass=PoolMeta):
    __name__ = 'ir.api.identity'

    def get_api_context(self):
        context = super().get_api_context()
        main_network = context.get('dist_network', None)
        if main_network is not None:
            Network = Pool().get('distribution.network')
            distributors = Network(main_network).distributors
            if distributors:
                context['distributors'] = [x.id for x in distributors]
        return context


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

    @classmethod
    def _identity_context_output_schema(cls):
        schema = super()._identity_context_output_schema()
        schema['properties']['distributors'] = {
            'type': 'array',
            'additionalItems': False,
            'items': OBJECT_ID_SCHEMA,
            'minItems': 1,
            }
        return schema


class APIProduct(metaclass=PoolMeta):
    __name__ = 'api.product'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._apis.update({
                'list_commercial_products': {
                    'description': 'Provides the list of commercial products '
                    'a given user can sell.',
                    'readonly': True,
                    'public': False,
                    },
                })

    @classmethod
    def describe_products(cls, products):
        results = super().describe_products(products)
        return cls._describe_products_update_commercial_products(results)

    @classmethod
    def _describe_products_update_commercial_products(cls, results):
        pool = Pool()
        Core = pool.get('api.core')
        Network = pool.get('distribution.network')

        network = Core._get_dist_network()

        # We want to return all products for which at least one distributor
        # "under" the current network is authorized
        commercial_per_product = defaultdict(lambda: defaultdict(list))
        products_per_ids = {x['id']: x for x in results}

        for distributor in (network.distributors
                if network else Network.search(
                    [('is_distributor', '=', True)])):
            for com_product in distributor.all_com_products:
                if com_product.product.id not in products_per_ids:
                    continue
                commercial_per_product[com_product.product.id][
                    com_product].append(distributor)

        new_results = []
        for product, commercial_products in commercial_per_product.items():
            com_products = []
            for com_product, distributors in commercial_products.items():
                com_data = cls._describe_commercial_product(com_product)
                com_data['distributors'] = sorted([
                        cls._describe_distributor(x) for x in distributors],
                    key=lambda x: x['code'])
                com_products.append(com_data)

            data = products_per_ids[product]
            data['commercial_products'] = sorted(com_products,
                key=lambda x: x['code'])
            new_results.append(data)

        return new_results

    @classmethod
    def _describe_commercial_product(cls, commercial_product):
        return {
            'id': commercial_product.id,
            'code': commercial_product.code,
            'name': commercial_product.name,
            }

    @classmethod
    def _describe_distributor(cls, distributor):
        return {
            'id': distributor.id,
            'code': distributor.code,
            'name': (distributor.party.full_name if distributor.party
                else distributor.name),
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
                'code': CODE_SCHEMA,
                'name': {'type': 'string'},
                'distributors': {
                    'type': 'array',
                    'additionalItems': False,
                    'minItems': 1,
                    'items': cls._describe_distributor_schema(),
                    },
                },
            'required': ['id', 'code', 'name', 'distributors'],
            }

    @classmethod
    def _describe_distributor_schema(cls):
        return {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'id': OBJECT_ID_SCHEMA,
                'code': CODE_SCHEMA,
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
                'distributors': [
                    {
                        'id': 13,
                        'code': '4125',
                        'name': 'My distributor',
                        },
                    ],
                },
            {
                'id': 2,
                'code': 'com_product_2',
                'name': 'Commercial Product 2',
                'distributors': [
                    {
                        'id': 321,
                        'code': '3512',
                        'name': 'My other distributor',
                        },
                    ],
                },
            ]
        return examples

    @classmethod
    def list_commercial_products(cls, parameters):
        product_list = []
        com_products = cls._find_commercial_products()

        for product in com_products:
            documents = [a for a in product.attachments if a.type == 'link'] \
                or []
            public_doc = cls._build_documents_list(documents)
            product_list.append({'code': product.code, 'name': product.name,
                'start_date': str(product.start_date), 'technical_product':
                {'code': product.product.code, 'name': product.product.name},
                'public_documents': public_doc})
        return product_list

    @classmethod
    def _find_commercial_products(cls):
        pool = Pool()
        DistNetwork = pool.get('distribution.network')
        API = pool.get('api')

        context = api_context()
        if 'dist_network' in context and context['dist_network']:
            network = DistNetwork(context['dist_network'])
            return network.all_com_products
        else:
            API.add_input_error({
                'type': 'cannot_find_distribution_network',
                })

    @classmethod
    def _build_documents_list(cls, documents):
        public_doc = []
        for document in documents:
            doc = {'name': document.name, 'url': document.link}
            public_doc.append(doc)
        return public_doc

    @classmethod
    def _list_commercial_products_schema(cls):
        return {}

    @classmethod
    def _list_commercial_products_output_schema(cls):
        return {
            'type': 'array',
            'additionalProperties': False,
            'properties': {
                'code': {'type': 'string'},
                'name': {'type': 'string'},
                'start_date': DATE_SCHEMA,
                'technical_product': {'code': 'string', 'name': 'string'},
                'public_documents': cls._public_document_output_schema(),
                },
            }

    @classmethod
    def _public_document_output_schema(cls):
        return {
            'type': 'array',
            'additionalProperties': False,
            'properties': {
                'name': {'type': 'string'},
                'url': {'type': 'string'},
                },
            }

    @classmethod
    def _list_commercial_products_examples(cls):
        return [{
            'input': None,
            'output': [
                {
                    'code': 'habitation',
                    'name': 'Assurance habitation',
                    'start_date': '2020-01-01',
                    'technical_product': {'code': 'house_product',
                            'name': 'habitation'},
                    'public_documents': [
                        {
                            'name': 'doc',
                            'url': 'http://google.fr',
                            },
                        ]
                    },
                ]}]


class APIContract(metaclass=PoolMeta):
    __name__ = 'api.contract'

    @classmethod
    def _create_contract(cls, contract_data, created):
        contract = super()._create_contract(contract_data, created)

        # Commercial product is a function field, so we do nothing...
        contract.dist_network = contract_data['dist_network']

        return contract

    @classmethod
    def _contract_convert(cls, data, options, parameters, minimum=False):
        pool = Pool()
        API = pool.get('api')
        Core = pool.get('api.core')

        super()._contract_convert(data, options, parameters, minimum=minimum)
        network = Core._get_dist_network()

        if network is None:
            API.add_input_error({
                    'type': 'missing_dist_network',
                    'data': {},
                    })
        else:
            data['dist_network'] = network

        if minimum is False or 'commercial_product' in data:
            data['commercial_product'] = API.instantiate_code_object(
                'distribution.commercial_product', data['commercial_product'])
        else:
            data['commercial_product'] = None

    @classmethod
    def _validate_contract_input(cls, data):
        super()._validate_contract_input(data)
        if not data['commercial_product']:
            return
        pool = Pool()
        API = pool.get('api')

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
        if not minimum:
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

    @classmethod
    def _simulate_examples(cls):
        examples = super()._simulate_examples()
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


class CommercialProductWithWebResources(WebUIResourceMixin):
    __name__ = 'distribution.commercial_product'

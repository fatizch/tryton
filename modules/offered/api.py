# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation

from trytond.pool import PoolMeta, Pool

from trytond.modules.coog_core.api import APIResourceMixin, OBJECT_ID_SCHEMA
from trytond.modules.coog_core.api import CODED_OBJECT_ARRAY_SCHEMA, CODE_SCHEMA
from trytond.modules.coog_core.api import MODEL_REFERENCE
from trytond.modules.api import APIMixin, DEFAULT_INPUT_SCHEMA


EXTRA_DATA_VALUES_SCHEMA = {
    'type': 'object',
    'additionalProperties': False,
    'patternProperties': {
        '^[a-z0-9_]*$': {
            'type': ['boolean', 'integer', 'string'],
            },
        },
    'additionalProperties': False,
    }


EXTRA_DATA_VALUES_SCHEMA = {
    'type': 'object',
    'additionalProperties': False,
    'patternProperties': {
        '^[a-z0-9_]*$': {
            'type': ['boolean', 'integer', 'string'],
            },
        },
    'additionalProperties': False,
    }


__all__ = [
    'APICore',
    'APIProduct',
    'APIResource',
    'ExtraData',
    ]


class APICore(metaclass=PoolMeta):
    __name__ = 'api.core'

    @classmethod
    def _extra_data_structure(cls, extra_data_list):
        '''
            Returns the standard way of communicating extra_data configurations
            for API V2
        '''
        per_key = {}
        conditions = defaultdict(list)

        def parse_structure(elem):
            if elem['code'] in per_key:
                return
            per_key[elem['code']] = {
                'code': elem['code'],
                'name': elem['name'],
                'type': elem['technical_kind'],
                'sequence': elem['sequence'],
                }
            if 'digits' in elem:
                # We only need the length of the non-integer part
                per_key[elem['code']]['digits'] = elem['digits'][1]
            if 'default' in elem:
                per_key[elem['code']]['default'] = elem['default']
            if 'selection' in elem:
                if elem.get('sorted', False):
                    selection = elem['selection']
                else:
                    selection = sorted(elem['selection'], key=lambda x: x[0])
                per_key[elem['code']]['selection'] = [
                    {'value': x[0], 'name': x[1], 'sequence': idx}
                    for idx, x in enumerate(selection)]
            if 'custom_resources' in elem:
                per_key[elem['code']]['custom_resources'] = \
                    elem['custom_resources']
            if 'sub_data' in elem:
                for operator, value, sub_structure in elem['sub_data']:
                    parse_structure(sub_structure)
                    conditions[sub_structure['code']].append({
                            'code': elem['code'],
                            'operator': operator,
                            'value': value,
                            })

        for structure in [x._get_structure() for x in extra_data_list]:
            parse_structure(structure)

        for code, sub_conditions in conditions.items():
            per_key[code]['conditions'] = sub_conditions

        return list(per_key.values())

    @classmethod
    def _extra_data_schema(cls):
        '''
            Returns a schema that matches a extra data definition in API V2
        '''
        return {
            'type': 'array',
            'items': {
                'oneOf': [
                    {
                        'type': 'object',
                        'additionalProperties': False,
                        'properties': {
                            'code': CODE_SCHEMA,
                            'name': {'type': 'string'},
                            'type': {
                                'type': 'string',
                                'enum': ['boolean', 'char', 'datetime',
                                    'date', 'integer'],
                                },
                            'sequence': {'type': 'integer'},
                            'conditions': {
                                'type': 'array',
                                'items': {
                                    'type': 'object',
                                    'properties': {
                                        'code': CODE_SCHEMA,
                                        'operator': {
                                            'type': 'string',
                                            'enum': ['='],
                                            },
                                        'value': {},
                                        },
                                    'additionalProperties': False,
                                    'required': ['code', 'operator', 'value'],
                                    },
                                'additionalItems': False,
                                },
                            'custom_resources': {},
                            'default': {'type': 'boolean'},
                            },
                        'required': ['code', 'name', 'type',
                            'sequence'],
                        },
                    {
                        'type': 'object',
                        'additionalProperties': False,
                        'properties': {
                            'code': CODE_SCHEMA,
                            'name': {'type': 'string'},
                            'type': {
                                'type': 'string',
                                'enum': ['selection'],
                                },
                            'sequence': {'type': 'integer'},
                            'selection': {
                                'type': 'array',
                                'items': {
                                    'type': 'object',
                                    'properties': {
                                        'value': {'type': 'string'},
                                        'name': {'type': 'string'},
                                        'sequence': {'type': 'integer'},
                                        },
                                    'additionalProperties': False,
                                    'required': ['value', 'name', 'sequence'],
                                    },
                                'additionalItems': False,
                                'minItems': 1,
                                },
                            'conditions': {
                                'type': 'array',
                                'items': {
                                    'type': 'object',
                                    'properties': {
                                        'code': CODE_SCHEMA,
                                        'operator': {
                                            'type': 'string',
                                            'enum': ['='],
                                            },
                                        'value': {},
                                        },
                                    'additionalProperties': False,
                                    'required': ['code', 'operator', 'value'],
                                    },
                                'additionalItems': False,
                                },
                            'custom_resources': {},
                            'default': {'type': 'string'},
                            },
                        'required': ['code', 'name', 'type',
                            'sequence', 'selection'],
                        },
                    {
                        'type': 'object',
                        'additionalProperties': False,
                        'properties': {
                            'code': CODE_SCHEMA,
                            'name': {'type': 'string'},
                            'type': {
                                'type': 'string',
                                'enum': ['numeric'],
                                },
                            'sequence': {'type': 'integer'},
                            'digits': {'type': 'integer', 'minimum': 0},
                            'conditions': {
                                'type': 'array',
                                'items': {
                                    'type': 'object',
                                    'properties': {
                                        'code': CODE_SCHEMA,
                                        'operator': {
                                            'type': 'string',
                                            'enum': ['='],
                                            },
                                        'value': {},
                                        },
                                    'additionalProperties': False,
                                    'required': ['code', 'operator', 'value'],
                                    },
                                'additionalItems': False,
                                },
                            'custom_resources': {},
                            },
                        'required': ['code', 'name', 'type',
                            'sequence'],
                        },
                    ],
                },
            'additionalItems': False,
            }

    @classmethod
    def _extra_data_convert(cls, data):
        '''
            Transforms a dictionary of extra_data into the relevant types.

            Raises APIInputError if conversions are not possible, or if the
            value does not match the extra data type
        '''
        pool = Pool()
        ExtraData = pool.get('extra_data')
        API = pool.get('api')

        result = {}
        for code, value in data.items():
            extra_definition = ExtraData.search([('name', '=', code)])
            if not extra_definition:
                API.add_input_error({
                        'type': 'unknown_extra_data',
                        'data': {
                            'code': code,
                            },
                        })
                continue
            structure = extra_definition[0]._get_structure()
            if structure['technical_kind'] == 'integer':
                if not isinstance(value, int):
                    API.add_input_error({
                            'type': 'extra_data_type',
                            'data': {
                                'extra_data': code,
                                'expected_type': 'integer',
                                'given_type': str(type(value)),
                                },
                            })
                    continue
                result[code] = value
            elif structure['technical_kind'] == 'char':
                if not isinstance(value, str):
                    API.add_input_error({
                            'type': 'extra_data_type',
                            'data': {
                                'extra_data': code,
                                'expected_type': 'string',
                                'given_type': str(type(value)),
                                },
                            })
                    continue
                result[code] = value
            elif structure['technical_kind'] == 'numeric':
                if isinstance(value, int) and not isinstance(value, bool):
                    pass
                elif not isinstance(value, str):
                    API.add_input_error({
                            'type': 'extra_data_type',
                            'data': {
                                'extra_data': code,
                                'expected_type': 'string',
                                'given_type': str(type(value)),
                                },
                            })
                    continue
                elif ('.' in value and len(value.split('.')[1]) >
                        structure['digits'][1]):
                    API.add_input_error({
                            'type': 'extra_data_conversion',
                            'data': {
                                'extra_data': code,
                                'expected_format': '1111.%s' % ('1' *
                                    structure['digits'][1]),
                                'given_value': value,
                                },
                            })
                    continue
                try:
                    result[code] = Decimal(value)
                except InvalidOperation:
                    API.add_input_error({
                            'type': 'extra_data_conversion',
                            'data': {
                                'extra_data': code,
                                'expected_format': '1111.%s' % ('1' *
                                    structure['digits'][1]),
                                'given_value': value,
                                },
                            })
                    continue
            elif structure['technical_kind'] == 'selection':
                if not isinstance(value, str):
                    API.add_input_error({
                            'type': 'extra_data_type',
                            'data': {
                                'extra_data': code,
                                'expected_type': 'string',
                                'given_type': str(type(value)),
                                },
                            })
                    continue
                if value not in [x[0] for x in structure['selection']]:
                    API.add_input_error({
                            'type': 'extra_data_conversion',
                            'data': {
                                'extra_data': code,
                                'expected_format': [x[0] for x in
                                    structure['selection']],
                                'given_value': value,
                                },
                            })
                    continue
                result[code] = value
            elif structure['technical_kind'] == 'date':
                if not isinstance(value, str):
                    API.add_input_error({
                            'type': 'extra_data_type',
                            'data': {
                                'extra_data': code,
                                'expected_type': 'string',
                                'given_type': str(type(value)),
                                },
                            })
                    continue
                try:
                    result[code] = datetime.strptime(value, '%Y-%m-%d').date()
                except ValueError:
                    API.add_input_error({
                            'type': 'extra_data_conversion',
                            'data': {
                                'extra_data': code,
                                'expected_format': 'YYYY-MM-DD',
                                'given_value': value,
                                },
                            })
                    continue
            elif structure['technical_kind'] == 'boolean':
                if value is not True and value is not False:
                    API.add_input_error({
                            'type': 'extra_data_type',
                            'data': {
                                'extra_data': code,
                                'expected_type': 'boolean',
                                'given_type': str(type(value)),
                                },
                            })
                    continue
                result[code] = value
        return result


class APIProduct(APIMixin):
    '''
        API model for all configuration related APIs
    '''
    __name__ = 'api.product'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._apis.update({
                'describe_products': {
                    'description': 'Provides the description for the products '
                    'given as parameters. If no product is given, it will '
                    'return the description for all available products',
                    'readonly': True,
                    'public': False,
                    }
                })

    @classmethod
    def describe_products(cls, products):
        result = []
        if not products:
            products = Pool().get('offered.product').search([])
        for product in products:
            result.append(cls._describe_product(product))
        return result

    @classmethod
    def _describe_product(cls, product):
        pool = Pool()
        ApiCore = pool.get('api.core')
        return {
            'id': product.id,
            'code': product.code,
            'name': product.name,
            'description': product.description or '',
            'extra_data': ApiCore._extra_data_structure(
                product.extra_data_def),
            'coverages': [
                cls._describe_coverage(x) for x in product.coverages],
            'packages': [cls._describe_package(x) for x in product.packages],
            'subscriber': cls._describe_subscriber(product),
            }

    @classmethod
    def _describe_coverage(cls, coverage):
        pool = Pool()
        ApiCore = pool.get('api.core')
        return {
            'id': coverage.id,
            'code': coverage.code,
            'name': coverage.name,
            'description': coverage.description or '',
            'extra_data': ApiCore._extra_data_structure(
                coverage.extra_data_def),
            }

    @classmethod
    def _describe_package(cls, package):
        return {
            'id': package.id,
            'code': package.code,
            'name': package.name,
            'options': [{'id': x.option.id, 'code': x.option.code}
                for x in package.option_relations],
            }

    @classmethod
    def _describe_subscriber(cls, product):
        if product.subscriber_kind == 'person':
            return {
                'model': 'party',
                'conditions': [
                    {'name': 'is_person', 'operator': '=', 'value': True},
                    ],
                'required': ['name', 'first_name', 'birth_date', 'email',
                    'addresses'],
                'fields': ['name', 'first_name', 'birth_date', 'email',
                    'phone_number', 'addresses'],
                }
        elif product.subscriber_kind == 'company':
            return {
                'model': 'party',
                'conditions': [
                    {'name': 'is_person', 'operator': '=', 'value': False},
                    ],
                'required': ['name', 'email', 'addresses'],
                'fields': ['name', 'email', 'phone_number', 'addresses'],
                }
        if product.subscriber_kind == 'all':
            return {
                'model': 'party',
                'required': ['name', 'first_name', 'birth_date', 'email',
                    'addresses'],
                'fields': ['name', 'first_name', 'birth_date', 'email',
                    'phone_number', 'is_person', 'addresses'],
                }

    @classmethod
    def _describe_products_convert_input(cls, parameters):
        if not parameters:
            return parameters

        pool = Pool()
        Api = pool.get('api')
        products = []
        for product in parameters['products']:
            products.append(
                Api.instantiate_code_object('offered.product', product))
        return products

    @classmethod
    def _describe_products_examples(cls):
        return [
            {
                'input': {},
                'output': [
                    {
                        'id': 1,
                        'code': 'product_1',
                        'name': 'Product 1',
                        'description': 'My Awesome Product 1',
                        'extra_data': [
                            {
                                'code': 'contract_duration',
                                'name': 'Contract Duration',
                                'type': 'selection',
                                'sequence': 1,
                                'selection': [
                                    {'name': '3 months', 'value': '3',
                                        'sequence': 1},
                                    {'name': '6 months', 'value': '6',
                                        'sequence': 2},
                                    {'name': '1 year', 'value': '12',
                                        'sequence': 3},
                                    {'name': '2 years', 'value': '24',
                                        'sequence': 4},
                                    ],
                                },
                            ],
                        'coverages': [
                            {
                                'id': 1,
                                'code': 'coverage_1',
                                'name': 'Coverage 1',
                                'description': 'My Uber-Awesome Coverage 1',
                                'extra_data': [
                                    {
                                        'code': 'coverage_amount',
                                        'name': 'Coverage Amount',
                                        'type': 'selection',
                                        'sequence': 1,
                                        'selection': [
                                            {'name': '1000', 'value': '1000',
                                                'sequence': 1},
                                            {'name': '2000', 'value': '2000',
                                                'sequence': 2},
                                            {'name': '5000', 'value': '5000',
                                                'sequence': 3},
                                            {'name': '10000', 'value': '10000',
                                                'sequence': 4},
                                            ],
                                        },
                                    ]
                                }
                            ],
                        'subscriber': {
                            'model': 'party',
                            'required': ['name', 'first_name', 'birth_date',
                                'email'], 'fields': ['name', 'first_name',
                                'birth_date', 'email', 'phone_number',
                                'is_person'],
                            },
                        'packages': [],
                        },
                    ],
                },
            {
                'input': {
                    'products': [{'id': 1}, {'code': 'test_product'}],
                    },
                'output': [
                    {
                        'id': 1,
                        'code': 'product_1',
                        'name': 'Product 1',
                        'description': 'My Awesome Product 1',
                        'extra_data': [
                            {
                                'code': 'contract_duration',
                                'name': 'Contract Duration',
                                'type': 'selection',
                                'sequence': 1,
                                'selection': [
                                    {'name': '3 months', 'value': '3',
                                        'sequence': 1},
                                    {'name': '6 months', 'value': '6',
                                        'sequence': 2},
                                    {'name': '1 year', 'value': '12',
                                        'sequence': 3},
                                    {'name': '2 years', 'value': '24',
                                        'sequence': 4},
                                    ],
                                },
                            ],
                        'coverages': [
                            {
                                'id': 1,
                                'code': 'coverage_1',
                                'name': 'Coverage 1',
                                'description': 'My Uber-Awesome Coverage 1',
                                'extra_data': [
                                    {
                                        'code': 'coverage_amount',
                                        'name': 'Coverage Amount',
                                        'type': 'selection',
                                        'sequence': 1,
                                        'selection': [
                                            {'name': '1000',
                                                'value': '1000',
                                                'sequence': 1},
                                            {'name': '2000',
                                                'value': '2000',
                                                'sequence': 2},
                                            {'name': '5000',
                                                'value': '5000',
                                                'sequence': 3},
                                            {'name': '10000',
                                                'value': '10000',
                                                'sequence': 4},
                                            ],
                                        },
                                    ],
                                }
                            ],
                        'subscriber': {
                            'model': 'party',
                            'required': ['name', 'first_name', 'birth_date',
                                'email'], 'fields': ['name', 'first_name',
                                'birth_date', 'email', 'phone_number',
                                'is_person'],
                            },
                        'packages': [],
                        },
                    {
                        'id': 2,
                        'code': 'test_product',
                        'name': 'Test Product',
                        'description': 'My Test Product',
                        'extra_data': [],
                        'coverages': [
                            {
                                'id': 2,
                                'code': 'test_coverage',
                                'name': 'Test Coverage',
                                'description': 'My Uber-Awesome Coverage 1',
                                'extra_data': [],
                                }
                            ],
                        'subscriber': {
                            'model': 'party',
                            'conditions': [
                                {'name': 'is_person', 'operator': '=', 'value':
                                    True},
                                ],
                            'required': ['name', 'first_name', 'birth_date',
                                'email'],
                            'fields': ['name', 'first_name', 'birth_date',
                                'email', 'phone_number'],
                            },
                        'packages': [
                            {
                                'id': 1,
                                'code': 'test_package',
                                'name': 'Test Package',
                                'options': [
                                    {'code': 'test_coverage'},
                                    ],
                                },
                            ],
                        },
                    ],
                },
            ]

    @classmethod
    def _describe_products_schema(cls):
        return {
            'anyOf': [
                DEFAULT_INPUT_SCHEMA,
                {
                    'type': 'object',
                    'properties': {
                        'products': CODED_OBJECT_ARRAY_SCHEMA,
                        },
                    'additionalProperties': False,
                    },
                ],
            }

    @classmethod
    def _describe_products_output_schema(cls):
        return {
            'type': 'array',
            'additionalItems': False,
            'items': cls._describe_product_schema(),
            }

    @classmethod
    def _describe_product_schema(cls):
        '''
            Returns the schema for one product, will be overriden in modules in
            order to add new properties
        '''
        return {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'id': OBJECT_ID_SCHEMA,
                'code': CODE_SCHEMA,
                'name': {'type': 'string'},
                'description': {'type': 'string'},
                'coverages': {
                    'type': 'array',
                    'additionalItems': False,
                    'items': cls._describe_coverage_schema(),
                    },
                'extra_data': Pool().get('api.core')._extra_data_schema(),
                'subscriber': MODEL_REFERENCE,
                'packages': {
                    'type': 'array',
                    'additionalItems': False,
                    'items': cls._describe_package_schema(),
                    },
                },
            'required': ['id', 'code', 'name', 'description', 'coverages',
                'extra_data', 'subscriber', 'packages'],
            }

    @classmethod
    def _describe_coverage_schema(cls):
        '''
            Returns the schema for one coverage, will be overriden in modules
            in order to add new properties
        '''
        return {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'id': OBJECT_ID_SCHEMA,
                'code': CODE_SCHEMA,
                'name': {'type': 'string'},
                'description': {'type': 'string'},
                'extra_data': Pool().get('api.core')._extra_data_schema(),
                },
            'required': ['id', 'code', 'name', 'description', 'extra_data'],
            }

    @classmethod
    def _describe_package_schema(cls):
        return {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'id': OBJECT_ID_SCHEMA,
                'code': CODE_SCHEMA,
                'name': {'type': 'string'},
                'options': CODED_OBJECT_ARRAY_SCHEMA,
                },
            'required': ['id', 'code', 'name', 'options'],
            }


class APIResource(metaclass=PoolMeta):
    __name__ = 'api.resource'

    @classmethod
    def create(cls, vlist):
        created = super().create(vlist)
        Pool().get('extra_data')._extra_data_cache.clear()
        return created

    @classmethod
    def delete(cls, ids):
        super().delete(ids)
        Pool().get('extra_data')._extra_data_cache.clear()

    @classmethod
    def write(cls, *args):
        super().write(*args)
        Pool().get('extra_data')._extra_data_cache.clear()


class ExtraData(APIResourceMixin):
    __name__ = 'extra_data'

    def _get_structure(self):
        res = super()._get_structure()
        if self.api_resources:
            res['custom_resources'] = {
                x.key: x.value
                for x in self.api_resources
                }
        return res

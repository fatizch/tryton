# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging

from trytond.pool import Pool
from trytond.model import Model
from trytond.server_context import ServerContext
from trytond.transaction import Transaction

from trytond.modules.coog_core import utils, model
from trytond.modules.rule_engine import check_args

from trytond.modules.api import APIMixin, date_from_api, APIInputError
from trytond.modules.api import APIServerError
from trytond.modules.api import DATE_SCHEMA
from trytond.modules.coog_core.api import CODED_OBJECT_SCHEMA, OBJECT_ID_SCHEMA
from trytond.modules.coog_core.api import CODE_SCHEMA
from trytond.modules.party_cog.api import PARTY_RELATION_SCHEMA
from trytond.modules.offered.api import EXTRA_DATA_VALUES_SCHEMA


logger = logging.getLogger('coog:api')


CONTRACT_SCHEMA = {
    'anyOf': [
        {
            'type': 'object',
            'additionalProperties': False,
            'properties': {'id': OBJECT_ID_SCHEMA},
            'required': ['id'],
            },
        {
            'type': 'object',
            'additionalProperties': False,
            'properties': {'number': CODE_SCHEMA},
            'required': ['number'],
            },
        ],
    }


__all__ = [
    'APIContract',
    'APIRuleRuntime',
    ]


class APIContract(APIMixin):
    'API Contract'
    __name__ = 'api.contract'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._apis.update({
                'subscribe_contracts': {
                    'public': False,
                    'readonly': False,
                    'description': 'Subscribe a contract using the provided '
                    'informations',
                    },
                'simulate': {
                    'public': False,
                    'readonly': True,
                    'description': 'Simulate contracts computations based '
                    'on provided informations',
                    },
                })

    @classmethod
    def _get_contract(cls, data, status_filter=None):
        '''
            Returns a contract based on a CONTRACT_SCHEMA input.
            If status_filter is not None, an error will be raised if the status
            of the contract does not match the provided value
        '''
        pool = Pool()
        API = pool.get('api')
        Contract = pool.get('contract')

        contract = None

        key, value = list(data.items())[0]
        if key == 'id':
            contract = API.instantiate_code_object('contract',
                {'id': value})
        else:
            assert key == 'number'
            matches = Contract.search(['OR',
                    [
                        ('status', 'in', ('quote', 'declined')),
                        ('quote_number', '=', value),
                        ],
                    [
                        ('status', 'not in', ('quote', 'declined')),
                        ('contract_number', '=', value),
                        ],
                    ])
            if not matches or len(matches) > 1:
                API.add_input_error({
                        'type': 'cannot_identify_contract',
                        'data': {
                            'key': key,
                            'value': value,
                            },
                        })
            else:
                contract, = matches
            if contract and status_filter and contract.status != status_filter:
                API.add_input_error({
                        'type': '%s_status_required' % status_filter,
                        'data': {
                            'contract': data.rec_name,
                            'status': data.status,
                            },
                        })
        return contract

    @classmethod
    def subscribe_contracts(cls, parameters):
        options = parameters.get('options', {})
        created = {}
        cls._subscribe_contracts_create_instances(parameters, created, options)
        cls._subscribe_contracts_execute(created, options)
        return cls._subscribe_contracts_result(created)

    @classmethod
    def _subscribe_contracts_create_priorities(cls):
        return ['parties', 'relations', 'contracts']

    @classmethod
    def _subscribe_contracts_create_instances(cls, parameters, created,
            options):
        for cur_model in cls._subscribe_contracts_create_priorities():
            getattr(cls, '_subscribe_contracts_create_%s' % cur_model)(
                parameters, created, options)

    @classmethod
    def _subscribe_contracts_create_parties(cls, parameters, created, options):
        Pool().get('api.party')._create_parties(parameters, created, options)

    @classmethod
    def _subscribe_contracts_create_relations(cls, parameters, created,
            options):
        Pool().get('api.party')._create_relations(parameters, created, options)

    @classmethod
    def _subscribe_contracts_create_contracts(cls, parameters, created,
            options):

        contracts = []
        for contract in parameters['contracts']:
            cls._update_contract_parameters(contract, created)
            cls._check_updated_contract_parameters(contract)
            contracts.append(cls._create_contract(contract, created))

        Pool().get('contract').save(contracts)
        created['contracts'] = {}
        for contract, data in zip(contracts, parameters['contracts']):
            created['contracts'][data['ref']] = contract

    @classmethod
    def _update_contract_parameters(cls, contract_data, created):
        '''
            Link newly created records in the contract data structure (ex:
            subscriber)
        '''
        if (isinstance(contract_data['subscriber'], dict) and
                    'ref' in contract_data['subscriber']):
            contract_data['subscriber'] = created['parties'][
                contract_data['subscriber']['ref']]

    @classmethod
    def _check_updated_contract_parameters(cls, contract_data):
        cls._check_contract_parameters_subscriber(contract_data)

    @classmethod
    def _check_contract_parameters_subscriber(cls, contract_data):
        API = Pool().get('api')
        product = contract_data['product']
        subscriber = contract_data['subscriber']
        if product.subscriber_kind == 'person':
            if not subscriber.is_person:
                API.add_input_error({
                        'type': 'bad_constraint',
                        'data': {
                            'field': 'contract.subscriber',
                            'comment': 'Should be a person',
                            },
                        })
        elif product.subscriber_kind == 'company':
            if subscriber.is_person:
                API.add_input_error({
                        'type': 'bad_constraint',
                        'data': {
                            'field': 'contract.subscriber',
                            'comment': 'Should not be a person',
                            },
                        })

    @classmethod
    def _create_contract(cls, contract_data, created):
        contract = Pool().get('contract')()
        contract.subscriber = contract_data['subscriber']
        contract.signature_date = contract_data['signature_date']
        contract.start_date = contract_data['start']
        contract.appliable_conditions_date = contract_data['conditions_date']

        contract.extra_datas = [
            {'date': None, 'extra_data_values': contract_data['extra_data']},
            ]
        contract.extra_data_values = contract_data['extra_data']

        contract.product = contract_data['product']
        contract.status = 'quote'
        contract.company = contract.product.company

        options = []
        for option_data in contract_data.get('coverages', []):
            options.append(cls._create_option(option_data, contract, created))
        contract.options = options

        return contract

    @classmethod
    def _create_option(cls, option_data, contract, created):
        option = Pool().get('contract.option')()
        option.coverage = option_data['coverage']
        option.versions = [
            {'date': None, 'extra_data': option_data['extra_data']},
            ]
        return option

    @classmethod
    def _subscribe_contracts_execute(cls, created, options):
        Contract = Pool().get('contract')
        methods = cls._subscribe_contracts_execute_methods(options)

        contracts = list(created['contracts'].values())

        for method_data in sorted(methods, key=lambda x: x['priority']):
            method_obj = getattr(Contract, method_data['name'])
            try:
                if model.is_class_or_dual_method(method_obj):
                    method_obj(contracts, *(method_data['params'] or []))
                else:
                    for contract in contracts:
                        method_obj(contract, *(method_data['params'] or []))
            except Exception as e:
                error = Pool().get('api').handle_error(e)
                if isinstance(error, APIServerError):
                    raise APIInputError([{
                                'type': method_data['error_type'],
                                'data': {},
                                }])
                raise error

    @classmethod
    def _subscribe_contracts_execute_methods(cls, options):
        if options.get('activate', False):
            return [
                {
                    'priority': 100,
                    'name': 'activate_contract',
                    'params': None,
                    'error_type': 'cannot_activate_contract',
                    },
                ]
        return []

    @classmethod
    def _subscribe_contracts_result(cls, created):
        result = Pool().get('api.party')._create_parties_result(created)

        result['contracts'] = []
        for ref, instance in created['contracts'].items():
            result['contracts'].append(
                {'ref': ref, 'id': instance.id, 'number': instance.rec_name})

        return result

    @classmethod
    def _subscribe_contracts_convert_input(cls, parameters, minimum=False):
        pool = Pool()
        PartyAPI = pool.get('api.party')

        parameters['parties'] = parameters.get('parties', [])
        parameters['relations'] = parameters.get('relations', [])

        options = parameters.get('options', {})
        for party in parameters.get('parties', []):
            PartyAPI._party_convert(party, options, parameters)
        for relation in parameters.get('relations', []):
            PartyAPI._relation_convert(relation, options, parameters)
        for contract in parameters['contracts']:
            cls._contract_convert(contract, options, parameters,
                minimum=minimum)
        return parameters

    @classmethod
    def _contract_convert(cls, data, options, parameters, minimum=False):
        pool = Pool()
        API = pool.get('api')
        Core = pool.get('api.core')
        PartyAPI = pool.get('api.party')

        data['product'] = API.instantiate_code_object('offered.product',
            data['product'])

        if 'start' in data:
            data['start'] = date_from_api(data['start'])
        else:
            data['start'] = utils.today()

        data['start_date'] = data['start']

        if 'signature_date' in data:
            data['signature_date'] = date_from_api(data['signature_date'])
        else:
            data['signature_date'] = data['start_date']

        if 'conditions_date' in data:
            data['conditions_date'] = date_from_api(data['conditions_data'])
        else:
            data['conditions_date'] = data['signature_date']

        subscriber = PartyAPI._party_from_reference(data['subscriber'],
            parties=parameters['parties'])
        if subscriber:
            data['subscriber'] = subscriber

        data['package'] = data.get('package', None)
        if data['package']:
            data['package'] = API.instantiate_code_object('offered.package',
                data['package'])

        data['coverages'] = data.get('coverages', [])
        for coverage_data in data['coverages']:
            cls._contract_option_convert(coverage_data, options, parameters,
                package=data['package'], minimum=minimum)

        if data['package']:
            cls._contract_apply_package(data)

        extra_data = data.get('extra_data', {})
        extra_data = Core._extra_data_convert(extra_data, ['contract'])
        data['extra_data'] = extra_data

    @classmethod
    def _contract_option_convert(cls, data, options, parameters, package=None,
            minimum=False):
        pool = Pool()
        API = pool.get('api')
        Core = pool.get('api.core')

        data['coverage'] = API.instantiate_code_object(
            'offered.option.description', data['coverage'])

        if package:
            cls._contract_option_check_package(data, options, parameters,
                package)

        extra_data = data.get('extra_data', {})
        extra_data = Core._extra_data_convert(extra_data, ['option'])
        data['extra_data'] = extra_data

    @classmethod
    def _contract_apply_package(cls, data):
        API = Pool().get('api')

        extra_data = data.get('extra_data', {})
        contract_extra_data = data['package']._contract_extra_data
        intersection = set(extra_data.keys()).intersection(
            set(contract_extra_data.keys()))
        if intersection:
            API.add_input_error({
                    'type': 'manual_package_extra_data',
                    'data': {
                        'package': data['package'].code,
                        'product': data['product'].code,
                        'extra_data': sorted(intersection),
                        },
                    })
        extra_data.update(contract_extra_data)
        data['extra_data'] = extra_data

        coverages = {x['coverage'].code for x in data['coverages']}
        package_coverages = {x.option.code
            for x in data['package'].option_relations if x.option.is_service}
        if coverages - package_coverages:
            API.add_input_error({
                    'type': 'extra_coverage',
                    'data': {
                        'package': data['package'].code,
                        'extra_coverages': sorted(
                            coverages - package_coverages),
                        },
                    })
        # Create missing minimum coverages
        for coverage_code in package_coverages - coverages:
            data['coverages'].append(cls._contract_create_package_option(
                    data['package'], coverage_code))

        data['extra_data'] = extra_data

    @classmethod
    def _contract_option_check_package(cls, data, options, parameters,
            package):
        pool = Pool()
        API = pool.get('api')

        package_data = None
        package_data = [x for x in package.option_relations
            if x.option.code == data['coverage'].code]
        if not package_data:
            API.add_input_error({
                    'type': 'package_with_manual_coverages',
                    'data': {
                        'package': package.code,
                        'package_contents': sorted(x.option.code
                            for x in package.option_relations),
                        'manual_coverage': data['coverage'].code,
                        },
                    })
        else:
            package_data, = package_data

        if not package_data.extra_data:
            return

        extra_data = data.get('extra_data', {})

        intersection = set(extra_data.keys()).intersection(
            set(package_data.extra_data.keys()))
        if intersection:
            API.add_input_error({
                    'type': 'manual_package_extra_data',
                    'data': {
                        'package': package.code,
                        'coverage': data['coverage'].code,
                        'extra_data': sorted(intersection),
                        },
                    })
        extra_data.update(package_data.extra_data)
        data['extra_data'] = extra_data

    @classmethod
    def _contract_create_package_option(cls, package, coverage_code):
        package_option, = [x for x in package.option_relations
            if x.option.code == coverage_code]
        return {
            'coverage': package_option.option,
            'extra_data': package_option.extra_data,
            }

    @classmethod
    def _subscribe_contracts_validate_input(cls, parameters):
        for contract_data in parameters['contracts']:
            cls._validate_contract_input(contract_data)
            for option_data in contract_data.get('coverages', []):
                cls._validate_contract_option_input(option_data)

    @classmethod
    def _validate_contract_input(cls, data):
        API = Pool().get('api')
        extra = data['extra_data']
        recomputed = data['product'].refresh_extra_data(extra.copy())
        if recomputed != extra:
            API.add_input_error({
                    'type': 'invalid_extra_data_for_product',
                    'data': {
                        'product': data['product'].code,
                        'extra_data': sorted(extra.keys()),
                        'expected_keys': sorted(recomputed.keys()),
                        },
                    })

        all_coverages = [x['coverage'] for x in data['coverages']]
        if len(set(all_coverages)) != len(all_coverages):
            API.add_input_error({
                    'type': 'duplicate_coverages',
                    'data': {
                        'product': data['product'].code,
                        'coverages': sorted(x.code for x in all_coverages),
                        },
                    })

        services = [x for x in all_coverages if x.is_service]
        if (not all(x in data['product'].coverages for x in services)
                or len(all_coverages) != len(services)):
            API.add_input_error({
                    'type': 'invalid_coverage_for_product',
                    'data': {
                        'product': data['product'].code,
                        'coverages': sorted(x.code for x in all_coverages),
                        },
                    })

        mandatory = {x for x in services
            if x.subscription_behaviour == 'mandatory'}
        product_mandatory = {x for x in data['product'].coverages
            if x.subscription_behaviour == 'mandatory' and x.is_service}
        if len(mandatory) != len(product_mandatory):
            API.add_input_error({
                    'type': 'missing_mandatory_coverage',
                    'data': {
                        'product': data['product'].code,
                        'coverages': sorted(x.code for x in services),
                        'mandatory_coverages': sorted(
                            x.code for x in product_mandatory),
                        },
                    })

    @classmethod
    def _validate_contract_option_input(cls, data):
        API = Pool().get('api')
        extra = data['extra_data']
        recomputed = data['coverage'].refresh_extra_data(extra.copy())
        if recomputed != extra:
            API.add_input_error({
                    'type': 'invalid_extra_data_for_coverage',
                    'data': {
                        'coverage': data['coverage'].code,
                        'extra_data': sorted(extra.keys()),
                        'expected_keys': sorted(recomputed.keys()),
                        },
                    })

    @classmethod
    def _subscribe_contracts_schema(cls, minimum=False):
        pool = Pool()
        PartyAPI = pool.get('api.party')
        return {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'parties': {
                    'type': 'array',
                    'additionalItems': False,
                    'items': PartyAPI._party_schema(),
                    },
                'relations': {
                    'type': 'array',
                    'additionalItems': False,
                    'items': PartyAPI._relation_schema(),
                    },
                'contracts': {
                    'type': 'array',
                    'additionalItems': False,
                    'items': cls._contract_schema(minimum=minimum),
                    'minItems': 1,
                    },
                'options': {
                    'type': 'object',
                    'additionalProperties': False,
                    'properties': cls._subscribe_contracts_options_schema(),
                    },
                },
            'required': ['contracts'],
            }

    @classmethod
    def _contract_schema(cls, minimum=False):
        '''
            Returns the schema for a contract.

            If 'minimum' is True, required fields will be limited to the
            absolute minimum.
        '''
        schema = {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'ref': {'type': 'string'},
                'subscriber': PARTY_RELATION_SCHEMA,
                'product': CODED_OBJECT_SCHEMA,
                'start': DATE_SCHEMA,
                'extra_data': EXTRA_DATA_VALUES_SCHEMA,
                'coverages': {
                    'type': 'array',
                    'additionalItems': False,
                    'items': cls._contract_option_schema(minimum=minimum),
                    },
                'package': CODED_OBJECT_SCHEMA,
                },
            'required': ['ref', 'product', 'subscriber'],
            }

        return schema

    @classmethod
    def _contract_option_schema(cls, minimum=False):
        return {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'coverage': CODED_OBJECT_SCHEMA,
                'extra_data': EXTRA_DATA_VALUES_SCHEMA,
                },
            'required': ['coverage'],
            }

    @classmethod
    def _subscribe_contracts_options_schema(cls):
        return {
            'activate': {'type': 'boolean'},
            }

    @classmethod
    def _subscribe_contracts_output_schema(cls):
        return {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'parties': {
                    'type': 'array',
                    'additionalItems': False,
                    'items': {
                        'type': 'object',
                        'additionalProperties': False,
                        'properties': {
                            'ref': {'type': 'string'},
                            'id': OBJECT_ID_SCHEMA,
                            },
                        'required': ['ref', 'id'],
                        },
                    },
                'contracts': {
                    'type': 'array',
                    'additionalItems': False,
                    'items': {
                        'type': 'object',
                        'additionalProperties': False,
                        'properties': {
                            'ref': {'type': 'string'},
                            'id': OBJECT_ID_SCHEMA,
                            'number': {'type': 'string'},
                            },
                        'required': ['ref', 'id', 'number'],
                        },
                    }
                },
            'required': ['contracts'],
            }

    @classmethod
    def _subscribe_contracts_examples(cls):
        return [
            {
                'input': {
                    'parties': [
                        {
                            'ref': '1',
                            'is_person': True,
                            'name': 'Doe',
                            'first_name': 'John',
                            'birth_date': '1997-03-10',
                            'gender': 'male',
                            'addresses': [
                                {
                                    'street': 'Somewhere along the street',
                                    'zip': '75002',
                                    'city': 'Paris',
                                    'country': 'fr',
                                    },
                                ],
                            'relations': [
                                {
                                    'ref': '2',
                                    'type': 'child',
                                    'to': {'id': 123456},
                                    },
                                ],
                            },
                        ],
                    'contracts': [
                        {
                            'ref': '1',
                            'product': {
                                'code': 'my_product',
                                },
                            'subscriber': {'ref': '1'},
                            'start': '2019-09-01',
                            'extra_data': {
                                'my_extra_data': 10,
                                'my_date_data': '2010-04-06',
                                },
                            'coverages': [
                                {
                                    'coverage': {'code': 'super_coverage'},
                                    'extra_data': {
                                        'my_option_data': False,
                                        },
                                    },
                                ],
                            },
                        ],
                    'relations': [
                        {
                            'ref': '1',
                            'type': 'child',
                            'from': {'ref': '1'},
                            'to': {'id': 10},
                            },
                        ],
                    'options': {
                        'activate': True,
                        },
                    },
                'output': {
                    'parties': [
                        {
                            'ref': '1',
                            'id': 123,
                            },
                        ],
                    'contracts': [
                        {
                            'ref': '1',
                            'id': 43324,
                            'number': 'CNT0000001',
                            },
                        ],
                    },
                },
            ]

    @classmethod
    def _init_contract_rule_engine_parameters(cls, contract_data, parameters):
        return {
            'api.parties': parameters.get('parties', []),
            'api.contract': contract_data,
            'api.extra_data': {
                'contract': contract_data.get('extra_data', {}),
                },
            }

    @classmethod
    def _init_contract_option_rule_engine_parameters(cls, contract_data,
            option_data, parameters):
        base = cls._init_contract_rule_engine_parameters(contract_data,
            parameters)
        base['api.option'] = option_data
        base['api.extra_data']['option'] = option_data.get('extra_data', {})
        return base

    @classmethod
    def simulate(cls, parameters):
        with Transaction().new_transaction() as transaction:
            with Transaction().set_context(_will_be_rollbacked=True,
                    _disable_validations=True):
                with Transaction().set_user(0):
                    try:
                        created = cls._simulate_create_contracts(
                            parameters)

                        cls._simulate_parse_created(created)
                        contracts = created['contract_instances']
                        cls._simulate_prepare_contracts(contracts,
                            parameters)

                        return cls._simulate_result(contracts, parameters,
                            created)
                    finally:
                        transaction.rollback()

    @classmethod
    def _simulate_result(cls, contracts, parameters, created):
        results = []
        for contract in contracts:
            result = {
                'product': {
                    'code': contract.product.code,
                    },
                'coverages': [{
                        'coverage': {'code': option.coverage.code},
                        } for option in contract.options],
                'ref': created['contract_ref_per_id'][contract.id],
                }
            package = contract.get_package()
            if package:
                result['package'] = {
                    'code': package.code,
                    }
            results.append(result)
        return results

    @classmethod
    def _simulate_parse_created(cls, created):
        Contract = Pool().get('contract')
        created['party_ref_per_id'] = {
            x['id']: x['ref'] for x in created['parties']}
        created['contract_ref_per_id'] = {
            x['id']: x['ref'] for x in created['contracts']}
        created['contract_instances'] = Contract.browse(
            [x['id'] for x in created['contracts']])

    @classmethod
    def _simulate_create_contracts(cls, parameters):
        # Make sure we do not inadvertently activate the contract :)
        parameters['options'] = {}

        return getattr(cls.subscribe_contracts, '__origin_function')(cls,
            parameters)

    @classmethod
    def _simulate_prepare_contracts(cls, contracts, parameters):
        Contract = Pool().get('contract')
        Contract.calculate(contracts)

    @classmethod
    def _simulate_schema(cls):
        schema = cls._subscribe_contracts_schema(minimum=True)
        for kind in schema['properties']['parties']['items']['oneOf']:
            kind['required'] = ['ref']
        return schema

    @classmethod
    def _simulate_convert_input(cls, parameters):
        cls._simulate_convert_input_parties(parameters)
        result = cls._subscribe_contracts_convert_input(parameters,
            minimum=True)
        return result

    @classmethod
    def _simulate_convert_input_parties(cls, parameters):
        for party_data in parameters.get('parties', []):
            if 'name' not in party_data:
                party_data['name'] = 'Temp Name %s' % party_data['ref']
            if 'is_person' in party_data:
                if 'first_name' not in party_data:
                    party_data['first_name'] = \
                        'Temp First Name %s' % party_data['ref']
                if 'gender' not in party_data:
                    party_data['gender'] = 'male'

    @classmethod
    def _simulate_output_schema(cls):
        return {
            'type': 'array',
            'items': cls._simulate_contract_output_schema(),
            }

    @classmethod
    def _simulate_contract_output_schema(cls):
        return {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'product': CODED_OBJECT_SCHEMA,
                'package': CODED_OBJECT_SCHEMA,
                'coverages': cls._simulate_coverages_output_schema(),
                'ref': {'type': 'string'},
                },
            }

    @classmethod
    def _simulate_coverages_output_schema(cls):
        return {
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {
                    'additionalProperties': False,
                    'coverage': CODED_OBJECT_SCHEMA,
                    }
                }
            }

    @classmethod
    def _simulate_examples(cls):
        return [{
                'input': {
                    'parties': [
                        {
                            'ref': '1',
                            'is_person': True,
                            'name': 'Doe',
                            'first_name': 'Father',
                            'birth_date': '1980-01-20',
                            'gender': 'male',
                            'addresses': [
                                {
                                    'street': 'Somewhere along the street',
                                    'zip': '75002',
                                    'city': 'Paris',
                                    'country': 'fr',
                                    },
                                ],
                            },
                        ],
                    'contracts': [
                        {
                            'ref': '1',
                            'product': {'code': 'AAA'},
                            'subscriber': {'ref': '1'},
                            'extra_data': {
                                'contract_1': '16.10',
                                'contract_2': False,
                                'contract_3': '2',
                                },
                            'coverages': [
                                {
                                    'coverage': {'code': 'ALP'},
                                    'extra_data': {
                                        'option_1': '6.10',
                                        'option_2': True,
                                        'option_3': '2',
                                        },
                                    },
                                {
                                    'coverage': {'code': 'BET'},
                                    'extra_data': {},
                                    },
                                ],
                            },
                        ],
                    'options': {
                        'activate': True,
                        },
                    },
                'output': [{
                        'coverages': [
                            {'coverage': {'code': 'ALP'}},
                            {'coverage': {'code': 'BET'}},
                            ],
                        'product': {'code': 'AAA'},
                        'ref': '1',
                        },
                    ],
                }]


class APIRuleRuntime(Model):
    'Rule Runtime'

    __name__ = 'api.rule_runtime'

    @classmethod
    def __post_setup__(cls):
        super().__post_setup__()
        cls._api_runtime = {
            '_re_%s' % x[8:]: getattr(cls, x)
            for x in dir(cls)
            if x.startswith('_re_api_')
            }

    @classmethod
    def get_runtime(cls):
        '''
            Will be called to replace the tree element during a rule execution
            with the appropriate API function.

            The classical usage will be:

            with ServerContext().set_context(
                    api_rule_context=ContractAPIRuleRuntime.get_runtime()):
                my_rule.execute(...)
        '''

        Function = Pool().get('rule_engine.function')

        # For testing, we assume test_tree_element
        if ServerContext().get('_test_api_tree_elements', False):
            return {'%s_node' % x: y
                for x, y in cls._api_runtime.items()}
        return {
            Function.search([('name', '=', x)])[0].translated_technical_name: y
            for x, y in cls._api_runtime.items()
            }

    @classmethod
    def _get_field(cls, data, field_name):
        if isinstance(data, dict):
            if field_name in data:
                return data[field_name]
        else:
            return getattr(data, field_name)
        raise AttributeError

    @classmethod
    def _get_party(cls, ref, args):
        API = Pool().get('api')
        for party in args.get('api.parties', []):
            if party['ref'] == ref:
                return party
        API.add_input_error({
                'type': 'unknown_party_reference',
                'data': {
                    'ref': ref,
                    },
                })

    @classmethod
    def _get_subscriber(cls, contract_data, args):
        API = Pool().get('api')

        if 'subscriber' not in contract_data:
            API.add_input_error({
                    'type': 'missing_rule_engine_argument',
                    'data': {
                        'field': 'contract.subscriber',
                        },
                    })

        subscriber = contract_data['subscriber']

        if isinstance(subscriber, dict):
            subscriber = cls._get_party(subscriber['ref'], args)

        return subscriber

    @classmethod
    @check_args('api.contract')
    def _re_api_get_contract_initial_start_date(cls, args):
        contract_data = args['api.contract']

        result = contract_data.get('start_date', None)
        if result is None:
            Pool().get('api').add_input_error({
                    'type': 'missing_rule_engine_argument',
                    'data': {
                        'field': 'contract.start_date',
                        },
                    })
        return result

    @classmethod
    @check_args('api.contract')
    def _re_api_get_contract_start_date(cls, args):
        return cls._re_api_get_contract_initial_start_date(args)

    @classmethod
    @check_args('api.contract')
    def _re_api_contract_conditions_date(cls, args):
        return cls._re_api_get_contract_initial_start_date(args)

    @classmethod
    @check_args('api.contract')
    def _re_api_contract_signature_date(cls, args):
        contract_data = args['api.contract']

        result = contract_data.get('signature_date', None)
        if result is None:
            Pool().get('api').add_input_error({
                    'type': 'missing_rule_engine_argument',
                    'data': {
                        'field': 'contract.signature_date',
                        },
                    })
        return result

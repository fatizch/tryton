# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool

from trytond.modules.coog_core.api import CODED_OBJECT_SCHEMA
from trytond.modules.rule_engine import check_args
from trytond.modules.party_cog.api import PARTY_RELATION_SCHEMA
from trytond.modules.offered.api import EXTRA_DATA_VALUES_SCHEMA

__all__ = [
    'APIContract',
    'RuleEngine',
    'APIRuleRuntime',
    ]


class APIContract(metaclass=PoolMeta):
    __name__ = 'api.contract'

    @classmethod
    def _update_contract_parameters(cls, contract_data, created):
        super()._update_contract_parameters(contract_data, created)
        for covered in contract_data.get('covereds', []):
            if 'party' in covered and 'ref' in covered['party']:
                covered['party'] = created['parties'][covered['party']['ref']]

    @classmethod
    def _check_updated_contract_parameters(cls, contract_data):
        super()._check_updated_contract_parameters(contract_data)
        for covered_data in contract_data.get('covereds', []):
            cls._check_contract_parameters_covereds(covered_data, contract_data)

    @classmethod
    def _check_contract_parameters_covereds(cls, data, contract_data):
        API = Pool().get('api')
        item_desc = data['item_descriptor']
        party = data.get('party', None)
        if item_desc.kind == 'person':
            if not party or not party.is_person:
                API.add_input_error({
                        'type': 'bad_constraint',
                        'data': {
                            'field': 'covered.party',
                            'comment': 'Should be a person',
                            },
                        })
        elif item_desc.kind == 'company':
            if not party or party.is_person:
                API.add_input_error({
                        'type': 'bad_constraint',
                        'data': {
                            'field': 'covered.party',
                            'comment': 'Should not be a person',
                            },
                        })
        elif item_desc.kind == 'party':
            if not party:
                API.add_input_error({
                        'type': 'bad_constraint',
                        'data': {
                            'field': 'covered',
                            'comment': 'Party is required',
                            },
                        })

    @classmethod
    def _create_contract(cls, contract_data, created):
        contract = super()._create_contract(contract_data, created)

        covereds = []
        for covered_data in contract_data.get('covereds', []):
            covereds.append(
                cls._create_covered(covered_data, contract, created))
        contract.covered_elements = covereds

        return contract

    @classmethod
    def _create_covered(cls, covered_data, contract, created):
        covered = Pool().get('contract.covered_element')()
        covered.item_desc = covered_data['item_descriptor']
        covered.party = covered_data.get('party', None)
        covered.versions = [
            {'date': None, 'extra_data': covered_data.get('extra_data', {})},
            ]

        options = []
        for option_data in covered_data['coverages']:
            options.append(
                cls._create_covered_option(
                    option_data, covered, contract, created))
        covered.options = options
        return covered

    @classmethod
    def _create_covered_option(cls, option_data, covered, contract, created):
        # Easy for now
        return cls._create_option(option_data, contract, created)

    @classmethod
    def _contract_convert(cls, data, options, parameters):
        super()._contract_convert(data, options, parameters)

        for covered_data in data.get('covereds', []):
            cls._contract_covered_convert(covered_data, options, parameters)

    @classmethod
    def _contract_covered_convert(cls, data, options, parameters):
        pool = Pool()
        API = pool.get('api')
        Core = pool.get('api.core')
        PartyAPI = pool.get('api.party')

        data['item_descriptor'] = API.instantiate_code_object(
            'offered.item.description', data['item_descriptor'])

        data['party'] = data.get('party', None)
        if data['party']:
            party = PartyAPI._party_from_reference(data['party'],
                parties=parameters['parties'])
            if party:
                data['party'] = party

        extra_data = data.get('extra_data', {})
        extra_data = Core._extra_data_convert(extra_data)
        data['extra_data'] = extra_data

        for coverage_data in data.get('coverages', []):
            cls._contract_option_convert(coverage_data, options, parameters)

    @classmethod
    def _subscribe_contracts_validate_input(cls, parameters):
        super()._subscribe_contracts_validate_input(parameters)

        for contract_data in parameters['contracts']:
            for covered_data in contract_data.get('covereds', []):
                cls._validate_covered_element_input(
                    covered_data, contract_data)
                for option_data in covered_data.get('coverages', []):
                    cls._validate_contract_option_input(option_data)

    @classmethod
    def _validate_contract_input(cls, data):
        super()._validate_contract_input(data)

        API = Pool().get('api')
        product = data['product']
        for covered_data in data.get('covereds', []):
            if covered_data['item_descriptor'] not in product.item_descriptors:
                API.add_input_error({
                        'type': 'invalid_item_desc_for_product',
                        'data': {
                            'product': data['product'].code,
                            'item_desc': covered_data['item_descriptor'].code,
                            'expected': sorted([
                                    x.code for x in product.item_descriptors]),
                            },
                        })

    @classmethod
    def _validate_covered_element_input(cls, data, contract_data):
        API = Pool().get('api')
        extra = data['extra_data']
        recomputed = data['item_descriptor'].refresh_extra_data(
            extra.copy())
        if recomputed != extra:
            API.add_input_error({
                    'type': 'invalid_extra_data_for_covered',
                    'data': {
                        'item_desc': data['item_descriptor'].code,
                        'extra_data': sorted(extra.keys()),
                        'expected_keys': sorted(recomputed.keys()),
                        },
                    })

        all_coverages = [x['coverage'] for x in data['coverages']]
        if not all(x.item_desc == data['item_descriptor']
                for x in all_coverages):
            API.add_input_error({
                    'type': 'invalid_coverage_for_covered',
                    'data': {
                        'item_desc': data['item_descriptor'].code,
                        'coverages': sorted(x.code for x in all_coverages),
                        },
                    })

        if len(set(all_coverages)) != len(all_coverages):
            API.add_input_error({
                    'type': 'duplicate_coverages',
                    'data': {
                        'item_desc': data['item_descriptor'].code,
                        'coverages': sorted(x.code for x in all_coverages),
                        },
                    })

        mandatory = {x for x in all_coverages
            if x.subscription_behaviour == 'mandatory'}
        product_mandatory = {x for x in contract_data['product'].coverages
            if x.subscription_behaviour == 'mandatory' and not x.is_service
            and x.item_desc == data['item_descriptor']}
        if len(mandatory) != len(product_mandatory):
            API.add_input_error({
                    'type': 'missing_mandatory_coverage',
                    'data': {
                        'item_desc': data['item_descriptor'].code,
                        'coverages': sorted(x.code for x in all_coverages),
                        'mandatory_coverages': sorted(
                            x.code for x in product_mandatory),
                        },
                    })

    @classmethod
    def _contract_schema(cls, minimum=False):
        schema = super()._contract_schema(minimum=minimum)
        schema['properties']['covereds'] = {
            'type': 'array',
            'additionalItems': False,
            'items': cls._covered_element_schema(minimum=minimum),
            }
        schema['required'] = [x for x in schema['required'] if x != 'coverages']

        if not minimum:
            schema['anyOf'] = [
                {'required': ['coverages']},
                {'required': ['covereds']},
                ]
        return schema

    @classmethod
    def _covered_element_schema(cls, minimum=False):
        schema = {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'item_descriptor': CODED_OBJECT_SCHEMA,
                'extra_data': EXTRA_DATA_VALUES_SCHEMA,
                'party': PARTY_RELATION_SCHEMA,
                'coverages': {
                    'type': 'array',
                    'additionalItems': False,
                    'items': cls._contract_option_schema(minimum=minimum),
                    },
                },
            'required': ['item_descriptor'],
            }

        if not minimum:
            schema['required'].append('coverages')

        return schema

    @classmethod
    def _subscribe_contracts_examples(cls):
        examples = super()._subscribe_contracts_examples()
        examples[0]['input']['contracts'][0]['covereds'] = [
            {
                'item_descriptor': {'code': 'my_item_desc'},
                'party': {'ref': '1'},
                'extra_data': {'my_extra_covered': 10},
                'coverages': [
                    {
                        'coverage': {'code': 'my_covered_coverage'},
                        'extra_data': {'extra_1': 'hello'},
                        },
                    ],
                },
            {
                'item_descriptor': {'code': 'my_item_desc'},
                'party': {'id': 12345},
                'extra_data': {'my_extra_covered': 20},
                'coverages': [
                    {
                        'coverage': {'code': 'my_covered_coverage'},
                        'extra_data': {'extra_1': 'hello'},
                        },
                    {
                        'coverage': {'code': 'my_other_coverage'},
                        'extra_data': {},
                        },
                    ],
                },
            ]
        return examples


class RuleEngine(metaclass=PoolMeta):
    __name__ = 'rule_engine'

    @classmethod
    def get_external_extra_data_def(cls, key, args):
        pool = Pool()
        ExtraData = pool.get('extra_data')

        if 'api.extra_data' not in args:
            return super().get_external_extra_data_def(key, args)

        # Look for extra data in the api.extra_data key
        extra_data_per_kind = args['api.extra_data']
        data = ExtraData._extra_data_struct(key)
        if data['kind'] not in extra_data_per_kind:
            return None
        return extra_data_per_kind[data['kind']].get(key, None)


class APIRuleRuntime(metaclass=PoolMeta):
    __name__ = 'api.rule_runtime'

    @classmethod
    @check_args('api.contract')
    def _re_api_get_subscriber_birthdate(cls, args):
        contract_data = args['api.contract']

        subscriber = cls._get_subscriber(contract_data, args)

        return cls._get_field(subscriber, 'birth_date')

    @classmethod
    @check_args('api.contract', 'api.option')
    def _re_api_get_option_initial_start_date(cls, args):
        return cls._re_api_get_contract_initial_start_date(args)

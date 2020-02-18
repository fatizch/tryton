# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool

from trytond.modules.coog_core.api import CODED_OBJECT_SCHEMA, CODE_SCHEMA
from trytond.modules.rule_engine import check_args
from trytond.modules.party_cog.api import PARTY_RELATION_SCHEMA
from trytond.modules.offered.api import EXTRA_DATA_VALUES_SCHEMA

__all__ = [
    'APIContract',
    'RuleEngine',
    'APIRuleRuntime',
    'APIParty',
    ]


class APIContract(metaclass=PoolMeta):
    __name__ = 'api.contract'

    @classmethod
    def _get_option(cls, contract, data):
        '''
            Identifies an option on a contract based on given data.

            The typical use case will have data including a party (for
            identifiying the covered element) and a coverage.
        '''
        pool = Pool()
        API = pool.get('api')

        if 'id' in data:
            return API.instantiate_code_object('contract.option',
                {'id': data['id']})
        elif 'party' in data:
            # Identify parent from covered_elements
            matches = [x for x in contract.covered_elements
                if x.party == data['party']]
            if len(matches) == 1:
                parent = matches[0]
            elif len(matches) == 0:
                API.add_input_error({
                        'type': 'unknown_party_on_contract',
                        'data': {
                            'party': data['party'].rec_name,
                            'contract': contract.rec_name,
                            },
                        })
            else:
                API.add_input_error({
                        'type': 'multiple_party_matches_on_contract',
                        'data': {
                            'party': data['party'].rec_name,
                            'contract': contract.rec_name,
                            },
                        })
        else:
            parent = contract

        for option in parent.options:
            if option.coverage == data['coverage']:
                return option

        API.add_input_error({
                'type': 'unknown_option_on_contract',
                'data': {
                    'parent': parent.rec_name,
                    'option': data['coverage'].name,
                    },
                })

    @classmethod
    def _update_contract_parameters(cls, contract_data, created):
        super()._update_contract_parameters(contract_data, created)
        for covered in contract_data.get('covereds', []):
            if 'party' in covered and 'ref' in covered['party']:
                covered['party'] = created['parties'][covered['party']['ref']]

    @classmethod
    def _check_updated_contract_parameters(cls, contract_data, options):
        super()._check_updated_contract_parameters(contract_data, options)
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
    def _contract_convert(cls, data, options, parameters, minimum=False):
        API = Pool().get('api')

        super()._contract_convert(data, options, parameters, minimum=minimum)

        for covered_data in data.get('covereds', []):
            cls._contract_covered_convert(covered_data, options, parameters,
                minimum=minimum)

        # Super call made sure that if there was a package on the product, the
        # configuration was consistent. We just need to check that if there is
        # no package on the contract, the configuration matches what we are
        # given
        covered_packages = sorted({x['package'].code
                for x in data.get('covereds', []) if x.get('package', None)})
        if (covered_packages and not data.get('package', None) and
                not data['product'].packages_defined_per_covered):
            API.add_input_error({
                    'type': 'per_contract_package',
                    'data': {
                        'product': data['product'].code,
                        'covered_packages': covered_packages,
                        },
                    })

    @classmethod
    def _contract_apply_package(cls, data):
        API = Pool().get('api')

        # If there are covered elements, the package behaviour is slightly
        # different from the basic use case. Packages are either forced on all
        # covered elements, or they are defined per covered elements
        if data.get('covereds', []):
            if data['product'].packages_defined_per_covered:
                # If there is a package, and it is "per covered", it must not
                # be set at the contract level
                API.add_input_error({
                        'type': 'per_covered_package',
                        'data': {
                            'product': data['product'].code,
                            'package': data['package'].code,
                            },
                        })
            else:
                # If there are covered element, and packages are not 'per
                # covered', we propagate the selected package to each covered
                # and let them handle it
                for covered_data in data['covereds']:
                    if covered_data.get('package', None):
                        API.add_input_error({
                                'code': 'global_package_configuration',
                                'data': {
                                    'product': data['product'].code,
                                    'forced_package': data['package'].code,
                                    },
                                })
                    else:
                        covered_data['package'] = {
                            'code': data['package'].code}

        # We still call super to set contract extra data, and define service
        # coverages
        return super()._contract_apply_package(data)

    @classmethod
    def _contract_covered_convert(cls, data, options, parameters,
            minimum=False):
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

        data['package'] = data.get('package', None)
        if data['package']:
            data['package'] = API.instantiate_code_object('offered.package',
                data['package'])

        data['coverages'] = data.get('coverages', [])
        for coverage_data in data['coverages']:
            cls._contract_option_convert(coverage_data, options, parameters,
                package=data['package'], minimum=minimum)

        extra_data = data.get('extra_data', {})

        if data['package']:
            covered_extra_data = data['package']._covered_extra_data
            intersection = set(extra_data.keys()).intersection(
                set(covered_extra_data.keys()))
            if intersection:
                API.add_input_error({
                        'type': 'manual_package_extra_data',
                        'data': {
                            'package': data['package'].code,
                            'item_descriptor': data['item_descriptor'].code,
                            'extra_data': sorted(intersection),
                            },
                        })
            extra_data.update(covered_extra_data)
            data['extra_data'] = extra_data

            coverages = {x['coverage'].code for x in data['coverages']}

            # Filter contract coverages
            package_coverages = {x.option.code
                for x in data['package'].option_relations
                if x.option.item_desc}
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

        extra_data = Core._extra_data_convert(extra_data, ['covered_element'])
        data['extra_data'] = extra_data

    @classmethod
    def _subscribe_contracts_validate_input(cls, parameters):
        super()._subscribe_contracts_validate_input(parameters)

        for contract_data in parameters['contracts']:
            for covered_data in contract_data.get('covereds', []):
                cls._validate_covered_element_input(
                    covered_data, contract_data, parameters.get('parties', []))
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
    def _validate_covered_element_input(cls, data, contract_data, parties):
        pool = Pool()
        API = pool.get('api')
        ExtraData = pool.get('extra_data')
        extra = data['extra_data']
        recomputed = data['item_descriptor'].refresh_extra_data(
            extra.copy())
        if not ExtraData.check_for_consistency(recomputed, extra):
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

        # test coherence between the party in covered and the referenced party
        if data['party'] and 'ref' in data['party']:
            party = next(party for party in parties
                if party['ref'] == data['party']['ref'])
            if 'extra_data' in party:
                cls._validate_party_extra_data(data, party)

    @classmethod
    def _validate_party_extra_data(cls, covered, party):
        API = Pool().get('api')
        common_keys = set(covered['extra_data']) & set(party['extra_data'])
        conflicting_keys = [key for key in common_keys
            if covered['extra_data'][key] != party['extra_data'][key]]
        if conflicting_keys:
            API.add_input_error({
                    'type': 'conflicting_extra_data',
                    'data': {
                        'codes': list(conflicting_keys),
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
                'package': CODED_OBJECT_SCHEMA,
                },
            'required': ['item_descriptor'],
            }

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

    @classmethod
    def _simulate_result(cls, contracts, parameters, created):
        results = super(APIContract, cls)._simulate_result(contracts,
            parameters, created)
        for i, contract in enumerate(contracts):
            descriptions = []
            for covered in contract.covered_elements:
                descriptions.append(cls._simulate_contract_covered_result(
                        covered, contract, created))
            results[i].update({'covereds': descriptions})
        return results

    @classmethod
    def _simulate_contract_covered_result(cls, covered, contract, created):
        covereds_parameters = \
            created['contract_parameters_per_id'][contract.id].get('covereds')
        desc = {'coverages': [cls._simulate_contract_extract_covered_option(
                    option) for option in covered.all_options]}
        if covered.party:
            covered_parameters = next((cov for cov in covereds_parameters
                if cov['party'].id == covered.party.id), None)
            if covered_parameters:
                package = covered_parameters.get('package')
                if package:
                    desc['package'] = {'code': package.code}
            created_party = created['party_ref_per_id'].get(
                covered.party.id)
            if created_party:
                desc['party'] = {'ref': created_party}
            else:
                desc['party'] = {
                    'id': covered.party.id,
                    'code': covered.party.code,
                    'name': covered.party.full_name,
                    }
        elif covered.name is not None:
            desc['name'] = covered.name
        return desc

    @classmethod
    def _simulate_contract_extract_covered_option(cls, option):
        return cls._simulate_contract_extract_option(option)

    @classmethod
    def _simulate_contract_output_schema(cls):
        schema = super(APIContract, cls)._simulate_contract_output_schema()
        schema['properties']['covereds'] = \
            cls._simulate_covereds_output_schema()
        return schema

    @classmethod
    def _simulate_covereds_output_schema(cls):
        return {
            'type': 'array',
            'items': {
                'type': 'object',
                'additionalProperties': False,
                'properties': {
                    'party': {
                        'type': 'object',
                        'oneOf': [
                            {
                                'additionalProperties': False,
                                'properties': {
                                    'ref': {'type': 'string'},
                                    },
                                'required': ['ref'],
                                },
                            {
                                'additionalProperties': False,
                                'properties': {
                                    'id': {'type': 'integer'},
                                    'code': CODE_SCHEMA,
                                    'name': {'type': 'string'},
                                    },
                                'required': ['id', 'code', 'name'],
                                },
                            ],
                    },
                    'name': {'type': 'string'},
                    'coverages': cls._simulate_coverages_output_schema(),
                    'package': CODED_OBJECT_SCHEMA,
                    },
                }
            }


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


class APIParty(metaclass=PoolMeta):
    __name__ = 'api.party'

    @classmethod
    def _create_party_examples(cls):
        examples = super()._create_party_examples()
        examples.append({
                'input': {
                    'parties': [{
                        'ref': '4',
                        'is_person': False,
                        'name': 'My company',
                        'contacts': [
                            {
                                'type': 'email',
                                'value': '123@456.com',
                                },
                            ],
                        'extra_data': {
                            'house_floor': 2,
                            },
                        },
                    ],
                    },
                'output': {
                    'parties': [{'ref': '4', 'id': 4}],
                    },
                })
        return examples

    @classmethod
    def _party_schema(cls):
        schema = super()._party_schema()
        for party_schema in schema['oneOf']:
            party_schema['properties']['extra_data'] = \
                EXTRA_DATA_VALUES_SCHEMA
        return schema

    @classmethod
    def _party_convert(cls, data, options, parameters):
        # Rules to get party extra data:
        # If current party is not a person
        #   -> extra data kind should only be party_company
        # If current party is a person indeed
        #   -> extra data kind could be both
        #      1. party_person
        #      2. covered_element with flag store_on_party = True
        super()._party_convert(data, options, parameters)
        APICore = Pool().get('api.core')
        party_extra_data = data.get('extra_data', {})

        if not data['is_person']:
            data['extra_data'] = APICore._extra_data_convert(
                party_extra_data, ['party_company'])
        else:
            data['extra_data'] = APICore._extra_data_convert(
                party_extra_data, ['party_person', 'covered_element'])
            cls._check_store_on_covered_extra_data(data)

    @classmethod
    def _check_store_on_covered_extra_data(cls, data):
        pool = Pool()
        API = pool.get('api')
        ExtraData = pool.get('extra_data')
        party_extra_data = data.get('extra_data', {})

        for code, value in party_extra_data.items():
            extra_definition, = ExtraData.search([('name', '=', code)])
            structure = extra_definition._get_structure()
            if not structure['store_on_party'] and \
                    structure['business_kind'] == 'covered_element':
                API.add_input_error({
                        'type': 'extra_data_store_on_party',
                        'data': {
                            'extra_data': code,
                            'expected_store_on_party': True,
                            'given_store_on_party':
                                structure['store_on_party'],
                            },
                        })

    @classmethod
    def _init_new_party(cls, data, options):
        party = super()._init_new_party(data, options)
        party.extra_data = {}
        return party

    @classmethod
    def _update_party(cls, party, data, options):
        super()._update_party(party, data, options)
        party.extra_data.update(data['extra_data'])
        party.extra_data = dict(party.extra_data)

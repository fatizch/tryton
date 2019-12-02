# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import json

from trytond.pool import PoolMeta, Pool

from trytond.modules.api import DEFAULT_INPUT_SCHEMA
from trytond.modules.coog_core.api import CODED_OBJECT_ARRAY_SCHEMA
from trytond.modules.coog_core.api import CODED_OBJECT_SCHEMA, REF_ID_SCHEMA
from trytond.modules.coog_core.api import OBJECT_ID_SCHEMA
from trytond.modules.offered.api import EXTRA_DATA_VALUES_SCHEMA


__all__ = [
    'APICore',
    'APICoreDistribution',
    'APICoreWebConfiguration',
    'APIContract',
    'APIContractDistribution',
    ]


class APICore(metaclass=PoolMeta):
    __name__ = 'api.core'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._apis.update({
                'list_questionnaires': {
                    'public': False,
                    'readonly': True,
                    'description': 'The list and configuration of available '
                    'questionnaires',
                    },
                'compute_questionnaire': {
                    'public': False,
                    'readonly': True,
                    'description': 'Computes the results of a questionnaire',
                    },
                })

    @classmethod
    def list_questionnaires(cls, questionnaires):
        result = []
        if not questionnaires:
            questionnaires = Pool().get('questionnaire').search([])
        for questionnaire in questionnaires:
            result.append(cls._questionnaire_definition(questionnaire))
        return result

    @classmethod
    def _questionnaire_definition(cls, questionnaire):
        return {
            'id': questionnaire.id,
            'code': questionnaire.code,
            'title': questionnaire.name,
            'description': questionnaire.description,
            'icon': questionnaire.icon_name,
            'sequence': questionnaire.sequence,
            'parts': [
                {
                    'id': x.id,
                    'title': x.name,
                    'mandatory': bool(x.mandatory),
                    'sequence': x.sequence,
                    'description': x.rule.description,
                    'questions': cls._extra_data_structure(x.extra_data_def),
                }
                for x in questionnaire.parts],
            }

    @classmethod
    def _list_questionnaires_convert_input(cls, parameters):
        if not parameters:
            return

        pool = Pool()
        Api = pool.get('api')
        questionnaires = []
        for questionnaire in parameters['questionnaires']:
            questionnaires.append(
                Api.instantiate_code_object('questionnaire', questionnaire))
        return questionnaires

    @classmethod
    def _list_questionnaires_schema(cls):
        return {
            'anyOf': [
                DEFAULT_INPUT_SCHEMA,
                {
                    'type': 'object',
                    'properties': {
                        'questionnaires': CODED_OBJECT_ARRAY_SCHEMA,
                        },
                    'additionalProperties': False,
                    },
                ],
            }

    @classmethod
    def _list_questionnaires_output_schema(cls):
        return {
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {
                    'id': OBJECT_ID_SCHEMA,
                    'code': {'type': 'string'},
                    'title': {'type': 'string'},
                    'description': {'type': 'string'},
                    'icon': {'type': 'string'},
                    'sequence': {'type': 'integer'},
                    'parts': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'id': OBJECT_ID_SCHEMA,
                                'title': {'type': 'string'},
                                'mandatory': {'type': 'boolean'},
                                'sequence': {'type': 'integer'},
                                'description': {'type': 'string'},
                                'questions': cls._extra_data_schema(),
                                },
                            'additionalProperties': False,
                            'required': ['id', 'title', 'sequence',
                                'description', 'questions'],
                            },
                        'minItems': 1,
                        },
                    'required': ['id', 'code', 'title', 'description',
                        'sequence', 'questionnaires'],
                    },
                'additionalProperties': False,
                },
            }

    @classmethod
    def _list_questionnaires_examples(cls):
        return [{
                'input': {
                    'questionnaires': [{'code': 'life_health'}],
                    },
                'output': [
                    {
                        'id': 1,
                        'code': 'life_health',
                        'title': 'Life / Health mixed offer',
                        'description': 'Enjoy our new Life / Health offer',
                        'parts': [
                            {
                                'id': 10,
                                'title': 'Health',
                                'sequence': 1,
                                'description': 'All your health needs',
                                'questions': [
                                    {
                                        'code': 'basic_needs',
                                        'name': 'Basic Healthcare Needs',
                                        'type': 'selection',
                                        'sequence': 1,
                                        'selection': [
                                            {'name': 'None', 'value': '0',
                                                'sequence': 1},
                                            {'name': 'Light', 'value': '1',
                                                'sequence': 2},
                                            {'name': 'Medium', 'value': '2',
                                                'sequence': 3},
                                            {'name': 'Important', 'value': '3',
                                                'sequence': 4},
                                            ],
                                        },
                                    ],
                                },
                            ],
                        },
                    ],
                },
            ]

    @classmethod
    def compute_questionnaire(cls, parameters):
        results = parameters['questionnaire'].calculate_questionnaire_result(
            parameters['parts'])
        return {
            'questionnaire': parameters['questionnaire'].id,
            'parts': [{'id': x['part'].id, 'results': x['results']}
                for x in results],
            }

    @classmethod
    def _compute_questionnaire_convert_input(cls, parameters):
        pool = Pool()
        API = pool.get('api')
        Part = pool.get('questionnaire.part')

        parameters['questionnaire'] = API.instantiate_code_object(
            'questionnaire', parameters['questionnaire'])

        parsed_parts = []
        for part_data in parameters['parts']:
            parsed_parts.append({
                    'part': Part(part_data['id']),
                    'answers': cls._extra_data_convert(part_data['answers'],
                        ['questionnaire']),
                    })
        parameters['parts'] = parsed_parts
        return parameters

    @classmethod
    def _compute_questionnaire_validate_input(cls, parameters):
        API = Pool().get('api')

        parts_per_id = {x.id: x for x in parameters['questionnaire'].parts}
        for part_data in parameters['parts']:
            if part_data['part'].id not in parts_per_id:
                API.add_input_error({
                        'type': 'unknown_questionnaire_part',
                        'data': {
                            'questionnaire': parameters['questionnaire'].code,
                            'part_id': part_data['part'].id,
                            'known_parts': sorted(parts_per_id.keys()),
                            },
                        })

            answers = part_data['answers']
            recomputed = part_data['part'].refresh_extra_data(answers.copy())
            if recomputed != answers:
                API.add_input_error({
                        'type': 'invalid_answer_for_questionnaire_part',
                        'data': {
                            'questionnaire': parameters['questionnaire'].code,
                            'part': part_data['part'].id,
                            'answers': sorted(answers.keys()),
                            'expected_keys': sorted(recomputed.keys()),
                            },
                        })

    @classmethod
    def _compute_questionnaire_schema(cls):
        return {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'questionnaire': CODED_OBJECT_SCHEMA,
                'parts': {
                    'type': 'array',
                    'additionalItems': False,
                    'items': {
                        'type': 'object',
                        'additionalProperties': False,
                        'properties': {
                            'id': OBJECT_ID_SCHEMA,
                            'answers': EXTRA_DATA_VALUES_SCHEMA,
                            },
                        'required': ['id', 'answers'],
                        },
                    },
                },
            'required': ['questionnaire', 'parts'],
            }

    @classmethod
    def _compute_questionnaire_output_schema(cls):
        return {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'questionnaire': {'type': 'integer'},
                'parts': {
                    'type': 'array',
                    'additionalItems': False,
                    'items': {
                        'type': 'object',
                        'additionalProperties': False,
                        'properties': {
                            'id': OBJECT_ID_SCHEMA,
                            'results': {
                                'type': 'array',
                                'additionalItems': False,
                                'items': {
                                    'type': 'object',
                                    'properties': {
                                        'score': {'type': 'integer'},
                                        'description': {'type': 'string'},
                                        'product': {'type': 'string'},
                                        'eligible': {'type': 'boolean'},
                                        'package': {'type': 'string'},
                                        },
                                    'additionalProperties': False,
                                    'required': ['score', 'description',
                                        'product', 'eligible'],
                                    },
                                },
                            },
                        'required': ['id', 'results'],
                        },
                    },
                },
            'required': ['questionnaire', 'parts'],
            }

    @classmethod
    def _compute_questionnaire_examples(cls):
        return [
            {
                'input': {
                    'questionnaire': {'id': 10},
                    'parts': [
                        {
                            'id': 1,
                            'answers': {
                                'extra_1': 10,
                                'extra_2': 'hello',
                                'extra_3': True,
                                },
                            },
                        {
                            'id': 2,
                            'answers': {
                                'extra_10': False,
                                },
                            },
                        ],
                    },
                'output': {
                    'questionnaire': 10,
                    'parts': [
                        {
                            'id': 1,
                            'results': [
                                {
                                    'score': 100,
                                    'description': 'Awesome choice',
                                    'product': 'my_awesome_product',
                                    'eligible': True,
                                    },
                                {
                                    'score': 50,
                                    'description':
                                    'Good choice, but not for you',
                                    'product': 'my_good_product',
                                    'eligible': False,
                                    },
                                {
                                    'score': 10,
                                    'description': 'Bad choice',
                                    'product': 'my_bad_product',
                                    'eligible': True,
                                    },
                                ],
                            },
                        {
                            'id': 2,
                            'results': [
                                {
                                    'score': 61,
                                    'description': 'No choice',
                                    'product': 'my_mandatory_product',
                                    'eligible': True,
                                    },
                                ],
                            },
                        ],
                    },
                },
            ]


class APICoreDistribution(metaclass=PoolMeta):
    __name__ = 'api.core'

    @classmethod
    def _compute_questionnaire_convert_input(cls, parameters):
        pool = Pool()

        parameters = super()._compute_questionnaire_convert_input(parameters)

        network = cls._get_dist_network()
        if network is not None:
            for part_parameter in parameters['parts']:
                part_parameter['dist_network'] = network
        else:
            pool.get('api').add_input_error({
                    'type': 'missing_dist_network',
                    'data': {},
                    })

        return parameters

    @classmethod
    def _compute_questionnaire_output_schema(cls):
        schema = super()._compute_questionnaire_output_schema()
        schema['properties']['parts']['items']['properties']['results'][
            'items']['properties']['commercial_product'] = {'type': 'string'}
        schema['properties']['parts']['items']['properties']['results'][
            'items']['required'].append('commercial_product')
        return schema

    @classmethod
    def _compute_questionnaire_examples(cls):
        examples = super()._compute_questionnaire_examples()
        for example in examples:
            for part in example['output']['parts']:
                for result in part['results']:
                    result['commercial_product'] = 'my_com_product'
        return examples


class APICoreWebConfiguration(metaclass=PoolMeta):
    __name__ = 'api.core'

    @classmethod
    def _questionnaire_definition(cls, questionnaire):
        definition = super()._questionnaire_definition(questionnaire)
        for part_def in definition['parts']:
            part = next(x for x in questionnaire.parts
                if part_def['id'] == x.id)
            extra_data_groups = getattr(part, 'extra_data_groups', None)
            if extra_data_groups is None:
                continue
            part_def.update({'groups': cls._extra_data_group_structure(
                        extra_data_groups
                    )})
        return definition

    @classmethod
    def _list_questionnaires_output_schema(cls):
        schema = super()._list_questionnaires_output_schema()
        schema['items']['properties']['parts']['items']['properties'][
            'groups'] = cls._extra_data_group_schema()
        return schema

    @classmethod
    def _list_questionnaires_examples(cls):
        examples = super()._list_questionnaires_examples()
        group_example = {
            'input': {
                'questionnaires': [{'code': 'life_health'}],
                },
            'output': [
                {
                    'id': 1,
                    'code': 'life_health',
                    'title': 'Life / Health mixed offer',
                    'description': 'Enjoy our new Life / Health offer',
                    'parts': [
                        {
                            'id': 10,
                            'title': 'Health',
                            'sequence': 1,
                            'description': 'All your health needs',
                            'questions': [],
                            'groups': [
                                {
                                    'extra_data': [{
                                            'code': 'refund_question',
                                            'name': 'Question on refund',
                                            'type': 'boolean',
                                            'sequence': 1,
                                            }],
                                    'title': 'Couverture globale',
                                    'description': '',
                                    },
                                {
                                    'extra_data': [
                                        {
                                            'code': 'question_1',
                                            'name': 'First question',
                                            'type': 'char',
                                            'sequence': 1,
                                            },
                                        {
                                            'code': 'question_2',
                                            'name': 'Second question',
                                            'type': 'datetime',
                                            'sequence': 2,
                                            },
                                        {
                                            'code': 'question_3',
                                            'name': 'Third question',
                                            'type': 'integer',
                                            'sequence': 3,
                                            },
                                    ],
                                    'title': 'Optique',
                                    'description': 'Vos besoins en matière \
                                    d\'optique',
                                    },
                            ]},
                        ],
                    },
                ]
            }
        examples.append(group_example)
        return examples


class APIContract(metaclass=PoolMeta):
    __name__ = 'api.contract'

    @classmethod
    def _subscribe_contracts_create_priorities(cls):
        return ['questionnaires'] + \
            super()._subscribe_contracts_create_priorities()

    @classmethod
    def _subscribe_contracts_create_questionnaires(cls, parameters, created,
            options):
        # Questionnaires are not (for now) shared accross contracts, so we must
        # copy their data for each contract. To do that, we just pass the input
        # as the created result
        created['questionnaires'] = {
            x['ref']: x for x in parameters.get('questionnaires', [])}

    @classmethod
    def _create_contract(cls, contract_data, created):
        contract = super()._create_contract(contract_data, created)

        if 'questionnaire' in contract_data:
            contract.questionnaires = [cls._create_questionnaire(contract_data)]

        return contract

    @classmethod
    def _create_questionnaire(cls, contract_data):
        pool = Pool()
        ContractQuestionnaire = pool.get('contract.questionnaire')
        Answer = pool.get('contract.questionnaire.answer')
        Result = pool.get('contract.questionnaire.result')

        questionnaire = ContractQuestionnaire()
        questionnaire.questionnaire = contract_data['questionnaire'][
            'questionnaire']

        answers, results = [], []

        for part in contract_data['questionnaire']['parts']:
            answers.append(Answer(part=part['id'], answers=part['answers']))
            results.append(Result(part=part['id'],
                    results_as_text=json.dumps(part['results'])))

        questionnaire.answers = answers
        questionnaire.results = results

        return questionnaire

    @classmethod
    def _update_contract_parameters(cls, contract_data, created):
        API = Pool().get('api')

        super()._update_contract_parameters(contract_data, created)

        if 'ref' in contract_data.get('questionnaire', {}):
            if (contract_data['questionnaire']['ref']
                    not in created['questionnaires']):
                API.add_input_error({
                        'type': 'unknown_reference',
                        'data': {
                            'field': 'contract.questionnaire',
                            'ref': contract_data['questionnaire']['ref'],
                            },
                        })
            else:
                contract_data['questionnaire'] = created['questionnaires'][
                    contract_data['questionnaire']['ref']]

    @classmethod
    def _subscribe_contracts_convert_input(cls, parameters, minimum=False):
        options = parameters.get('options', {})
        for questionnaire in parameters.get('questionnaires', []):
            cls._questionnaire_convert(questionnaire, options, parameters)

        return super()._subscribe_contracts_convert_input(parameters,
            minimum=minimum)

    @classmethod
    def _questionnaire_convert(cls, data, options, parameters):
        pool = Pool()
        API = pool.get('api')
        Core = pool.get('api.core')

        data['questionnaire'] = API.instantiate_code_object(
            'questionnaire', data['questionnaire'])

        for part in data['parts']:
            API.instantiate_code_object(
                'questionnaire.part', {'id': part['id']})
            answers = part.get('answers', {})
            answers = Core._extra_data_convert(answers, ['questionnaire'])
            part['answers'] = answers

            for choice in part['results']:
                # Just check it exists, we do not actually need it later
                API.instantiate_code_object('offered.product',
                    {'code': choice['product']})

    @classmethod
    def _subscribe_contracts_schema(cls, minimum=False):
        schema = super()._subscribe_contracts_schema(minimum=minimum)
        schema['properties']['questionnaires'] = {
            'type': 'array',
            'additionalItems': False,
            'items': cls._questionnaire_schema(),
            }
        return schema

    @classmethod
    def _contract_schema(cls, minimum=False):
        schema = super()._contract_schema(minimum=minimum)
        schema['properties']['questionnaire'] = REF_ID_SCHEMA
        return schema

    @classmethod
    def _questionnaire_schema(cls):
        return {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'ref': {'type': 'string'},
                'questionnaire': CODED_OBJECT_SCHEMA,
                'parts': {
                    'type': 'array',
                    'additionalItems': False,
                    'items': {
                        'type': 'object',
                        'additionalProperties': False,
                        'properties': {
                            'id': OBJECT_ID_SCHEMA,
                            'answers': EXTRA_DATA_VALUES_SCHEMA,
                            'results': {
                                'type': 'array',
                                'additionalItems': False,
                                'items': {
                                    'type': 'object',
                                    'properties': {
                                        'score': {'type': 'integer'},
                                        'description': {'type': 'string'},
                                        'product': {'type': 'string'},
                                        'package': {'type': 'string'},
                                        'eligible': {'type': 'boolean'},
                                        'selected': {'type': 'boolean'},
                                        },
                                    'additionalProperties': False,
                                    'required': ['score', 'description',
                                        'product', 'eligible'],
                                    },
                                },
                            },
                        'required': ['id', 'answers', 'results'],
                        },
                    },
                },
            'required': ['ref', 'questionnaire', 'parts'],
            }

    @classmethod
    def _subscribe_contracts_examples(cls):
        examples = super()._subscribe_contracts_examples()
        examples[-1]['input']['questionnaires'] = [
            {
                'ref': '1',
                'questionnaire': {'code': 'test_questionnaire'},
                'parts': [
                    {
                        'id': 1,
                        'answers': {
                            'lot_of_money': 'yes',
                            'wants_the_best': 'yes',
                            },
                        'results': [
                            {
                                'score': 100,
                                'description': 'Wonderful Choice',
                                'product': 'my_awesome_product',
                                'eligible': True,
                                'selected': False,
                                },
                            {
                                'score': 50,
                                'description': 'Good Choice',
                                'product': 'my_product',
                                'eligible': True,
                                'selected': True,
                                },
                            {
                                'score': 10,
                                'description': 'Bad Choice',
                                'product': 'inapropriate_product',
                                'eligible': False,
                                'selected': False,
                                },
                            ],
                        },
                    {
                        'id': 2,
                        'answers': {
                            'love_nurses': 'yes',
                            'requires_good_food': 'no',
                            },
                        'results': [
                            {
                                'score': 80,
                                'description': 'Why not',
                                'product': 'another_product',
                                'eligible': True,
                                'selected': False,
                                },
                            ],
                        },
                    ],
                }]
        examples[-1]['input']['contracts'][0]['questionnaire'] = {'ref': '1'}
        return examples


class APIContractDistribution(metaclass=PoolMeta):
    __name__ = 'api.contract'

    @classmethod
    def _questionnaire_schema(cls):
        schema = super()._questionnaire_schema()
        schema['properties']['parts']['items']['properties']['results'][
            'items']['properties']['commercial_product'] = {'type': 'string'}
        schema['properties']['parts']['items']['properties']['results'][
            'items']['required'].append('commercial_product')
        return schema

    @classmethod
    def _questionnaire_convert(cls, data, options, parameters):
        super()._questionnaire_convert(data, options, parameters)

        pool = Pool()
        API = pool.get('api')

        for part in data['parts']:
            for choice in part['results']:
                API.instantiate_code_object('distribution.commercial_product',
                    {'code': choice['commercial_product']})

    @classmethod
    def _subscribe_contracts_examples(cls):
        examples = super()._subscribe_contracts_examples()
        for part in examples[-1]['input']['questionnaires'][0]['parts']:
            for result in part['results']:
                result['commercial_product'] = ('%s_com_product' %
                    result['product'])
        return examples

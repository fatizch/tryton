# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool

from trytond.modules.api import DEFAULT_INPUT_SCHEMA, APIInputError
from trytond.modules.coog_core.api import CODED_OBJECT_ARRAY_SCHEMA
from trytond.modules.coog_core.api import CODED_OBJECT_SCHEMA
from trytond.modules.offered.api import EXTRA_DATA_VALUES_SCHEMA


__all__ = [
    'APICore',
    'APICoreDistribution',
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
                    'id': {'type': 'integer'},
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
                                'id': {'type': 'integer'},
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
                    'answers': cls._extra_data_convert(part_data['answers']),
                    })
        parameters['parts'] = parsed_parts
        return parameters

    @classmethod
    def _compute_questionnaire_validate_input(cls, parameters):
        parts_per_id = {x.id: x for x in parameters['questionnaire'].parts}
        for part_data in parameters['parts']:
            if part_data['part'].id not in parts_per_id:
                raise APIInputError([{
                            'type': 'unknown_questionnaire_part',
                            'data': {
                                'questionnaire':
                                parameters['questionnaire'].code,
                                'part_id': part_data['part'].id,
                                'known_parts': sorted(parts_per_id.keys()),
                                },
                            }])

            answers = part_data['answers']
            recomputed = part_data['part'].refresh_extra_data(answers.copy())
            if recomputed != answers:
                raise APIInputError([{
                            'type': 'invalid_answer_for_questionnaire_part',
                            'data': {
                                'questionnaire':
                                parameters['questionnaire'].code,
                                'part': part_data['part'].id,
                                'answers': sorted(answers.keys()),
                                'expected_keys': sorted(recomputed.keys()),
                                },
                            }])

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
                            'id': {'type': 'integer'},
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
                            'id': {'type': 'integer'},
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

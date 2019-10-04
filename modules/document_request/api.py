# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms
import datetime
import jwt
import base64
from trytond.modules.report_engine import Printable

from collections import defaultdict

from trytond.config import config
from trytond.model.exceptions import AccessError
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction

from trytond.modules.api.api.core import date_for_api
from trytond.modules.api import APIInputError
from trytond.modules.coog_core import fields, utils

from trytond.modules.offered.api import EXTRA_DATA_VALUES_SCHEMA

__all__ = [
    'APIParty',
    ]
# TODO: properly manage preriquisite


class DocumentTokenMixin(Printable):
    '''
    Allows to generate a signed, duration limited,
    renewable json web token on an model, via the generate_document_token
    method.

    The document token can then be used in an API to retrieve the
    document request lines associated to the token payload:

        - The object matching the token can be retrieved using the staticmethod
            "get_object_from_document_token"
        - The matching document request lines can be retrieved by calling the
            "get_documents_data" instance method, and by implementing
            "retrieve_party_document_request_lines" on the object
    '''

    document_token = fields.Char('Document Token', readonly=True,
        help='This token allows to retrieve document requests '
        'linked to the holder')

    def generate_document_token(self):
        pool = Pool()
        current_token = self.document_token
        if current_token:
            try:
                self._decode_document_token(current_token)
            except jwt.exceptions.ExpiredSignatureError:
                pass
            else:
                return

        data = self._generate_document_token_data()
        jwt_secret = config.get('document_api', 'document_token_secret')
        encoded_jwt = jwt.encode(data, jwt_secret, algorithm='HS256')
        self.document_token = encoded_jwt.decode('utf8')
        self.save()
        pool.get('event').notify_events([self], 'document_token_generation')

    @staticmethod
    def get_object_from_document_token(document_token):
        return DocumentTokenMixin._instanciate_object_from_payload(
            DocumentTokenMixin._get_document_token_payload(document_token))

    def _generate_document_token_data(self):
        return {
            'exp': self._get_document_token_expiration(),
            'for_object': str(self),
            }

    @staticmethod
    def _get_document_token_payload(document_token):
        try:
            payload = DocumentTokenMixin._decode_document_token(
                document_token)
        except jwt.exceptions.InvalidSignatureError:
            raise APIInputError([{
                    'type': 'invalid_document_token',
                    'data': {'token': document_token},
                        }])
        return payload

    @staticmethod
    def _instanciate_object_from_payload(payload):
        pool = Pool()
        for_object = payload['for_object']
        model_, id_ = for_object.split(',')
        try:
            object_ = pool.get(model_)(id_)
        except AccessError:
            raise APIInputError([{'type': 'The payload is erroneous'}])
        return object_

    def _get_document_token_expiration(self):
        jwt_duration = config.getint('document_api',
            'document_token_expiration_minutes') or 60 * 24 * 2
        return datetime.datetime.utcnow() + datetime.timedelta(
            minutes=jwt_duration)

    @staticmethod
    def _decode_document_token(document_token):
        jwt_secret = config.get('document_api', 'document_token_secret')
        payload = jwt.decode(document_token, jwt_secret,
            algorithms=['HS256'])
        return payload

    def get_documents_data(self):
        party = self.get_contact()

        lines = self.retrieve_party_document_request_lines(party)
        return {'party': party, 'document_request_lines': lines,
            'for_object': self}

    def retrieve_party_document_request_lines(self, party):
        raise NotImplementedError


class APIParty(metaclass=PoolMeta):
    __name__ = 'api.party'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._apis.update(
            {
                'token_document_requests': {
                    'description': 'Returns a party\'s document requests',
                    'readonly': True,
                    'public': True,
                },
                'token_upload_documents': {
                    'description': 'Allow to upload attachment to '
                    'document requests',
                    'readonly': False,
                    'public': True,
                },
                'token_submit_document_answers': {
                    'description': 'Submit answers to a document\'s questions',
                    'readonly': False,
                    'public': True,
                }
            }
        )

    """*** Start Document requests API ***"""
    @classmethod
    def token_document_requests(cls, parameters):
        return cls._build_token_document_requests_response(parameters)

    @classmethod
    def _build_token_document_requests_response(cls, parameters):
        object_ = parameters['for_object']
        documents_data = object_.get_documents_data()
        party = documents_data['party']
        response = {
            'informed_consent': [],
            'documents_to_fill': [],
            'documents_to_upload': [],
            'party_data': {'party': {
                    'name': party.name,
                    'first_name': party.first_name,
                    'birth_data': date_for_api(party.birth_date)
                    if party.birth_date else '',
                    }
                }
            }
        for l in documents_data['document_request_lines']:
            line_data = cls._build_request_line_data(l)
            if line_data.get('questions') and l.document_desc.prerequisite:
                response['informed_consent'].append(line_data)
            elif line_data.get('questions'):
                response['documents_to_fill'].append(line_data)
            else:
                response['documents_to_upload'].append(line_data)
        return response

    @classmethod
    def _build_request_line_data(cls, line):
        pool = Pool()
        ApiCore = pool.get('api.core')
        line_data = {
            'name': line.document_desc.name or '',
            'id': line.id,
            }
        if line.extra_data:
            questions = ApiCore._extra_data_structure(
                line.document_desc.extra_data_def)
            line_data['questions'] = cls._format_sub_questions(questions)
            line_data['status'] = line.data_status
        else:
            mapping = {'valid': 'done', 'invalid': 'refused',
                'waiting_validation': 'waiting_validation'}
            line_data['status'] = mapping[line.attachment.status] \
                if line.attachment else 'waiting'

            line_data['reception_date'] = date_for_api(line.reception_date) or \
                date_for_api(line.first_reception_date)
            line_data['validation_date'] = date_for_api(
                line.attachment.status_change_date) if line.attachment and \
                line.attachment.status == 'valid' else ''
            line_data['refusal_date'] = date_for_api(
                line.attachment.status_change_date) if line.attachment and \
                line.attachment.status == 'invalid' else ''
            line_data['reason'] = (line.details or '') if line.attachment and \
                line.attachment.status == 'invalid' else ''
        return line_data

    @classmethod
    def _format_sub_questions(cls, extra_data_struture):
        all_parents = defaultdict(list)

        def get_parent(extra_data):
            conditions = extra_data.get('conditions')
            if not conditions:
                return None
            return conditions[0].get('code')

        for extra_data in extra_data_struture:
            all_parents[get_parent(extra_data)].append(extra_data)

        parent_tree = all_parents[None]

        def build_tree(base_tree):
            for parent in base_tree:
                parent['questions'] = build_tree(all_parents[parent['code']])
            return base_tree

        return build_tree(parent_tree)

    @classmethod
    def _token_document_requests_schema(cls):
        return {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'document_token': {'type': 'string'},
                },
            'required': ['document_token']
        }

    @classmethod
    def _token_document_requests_output_schema(cls):
        return {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'informed_consent': {
                    'type': 'array',
                    'items': cls._schema_for_single_document_request(),
                    'additionalItems': False,
                    },
                'documents_to_fill': {
                    'type': 'array',
                    'items': cls._schema_for_single_document_request(),
                    'additionalItems': False,
                    },
                'documents_to_upload': {
                    'type': 'array',
                    'items': cls._schema_for_single_document_request(),
                    'additionalItems': False,
                    },
                'party_data': {
                    'type': 'object',
                    'properties': {
                        'name': {'type': 'string'},
                        'first_name': {'type': 'string'},
                        'birth_data': {'type': 'string'},
                        },
                    },
            },
            'required': ['informed_consent', 'documents_to_fill',
                    'documents_to_upload', 'party_data']
        }

    @classmethod
    def _schema_for_single_document_request(cls):
        return {
            'type': 'object',
            'properties': {
                'name': {'type': 'string'},
                'id': {'type': 'integer'},
                'filename': {'type': 'string'},
                'status': {'type': 'string'},
                'questions': cls._questions_schema(),
                'required': ['id'],
                }
            }

    @classmethod
    def _questions_schema(cls):
        APICore = Pool().get('api.core')
        question_schema = APICore._extra_data_schema()
        items = question_schema['items']['oneOf']
        for item in items:
            item['properties']['questions'] = {'type': 'array'}
        return question_schema

    @classmethod
    def _token_document_requests_examples(cls):
        return [
            {
                'input': {
                    'document_token': 'some_jwt',
                    },
                'output': {
                    "informed_consent": [],
                    "documents_to_fill": [
                        {
                            "name": "Mon Questionnaire",
                            "status": "done",
                            "filename": "id copy.png",
                            "questions": [
                                {
                                    "code": "etes_vous_fumeur",
                                    "name": "Etes vous fumeur ?",
                                    "type": "selection",
                                    "sequence": 53,
                                    "selection": [
                                        {
                                            "value": "oui",
                                            "name": "Oui",
                                            "sequence": 0
                                            },
                                        {
                                            "value": "non",
                                            "name": "Non",
                                            "sequence": 1
                                            }
                                        ]
                                    }
                                ]
                            }
                        ],
                    "documents_to_upload": [
                        {
                            "name": "certificate",
                            "id": 812,
                            "status": "waiting",
                            "filename": ""
                            }
                        ],
                    "party_data": {
                        "party": {
                            "name": "DOE",
                            "first_name": "Daisy",
                            "birth_data": "1981-04-11"
                            }
                        }
                    }
                }
        ]

    @classmethod
    def _common_document_token_conversion(cls, parameters):
        document_token = parameters.get('document_token')
        object_ = DocumentTokenMixin.get_object_from_document_token(
            document_token)
        parameters['for_object'] = object_
        return parameters

    @classmethod
    def _token_document_requests_convert_input(cls, parameters):
        return cls._common_document_token_conversion(parameters)

    """*** End Document Requests API Methods ***"""

    """↓↓↓↓ Start Upload Documents API Methods ↓↓↓↓"""

    @classmethod
    def token_upload_documents(cls, data):
        pool = Pool()
        DocumentRequestLine = pool.get('document.request.line')
        Attachment = pool.get('ir.attachment')
        line = data['request_line']

        with Transaction().set_user(0):
            attachment = Attachment(
                resource=line.for_object if
                line.for_object.__name__ == 'contract'
                else line.for_object.contract,
                document_desc=line.document_desc,
                status='waiting_validation',
                name=data['filename'],
                data=data['binary_data'])
            line.attachment = attachment
            if not line.first_reception_date:
                line.first_reception_date = utils.today()
            DocumentRequestLine.save([line])
        return 'ok'

    @classmethod
    def _token_upload_documents_schema(cls):
        return {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'id': {'type': 'string'},
                'filename': {'type': 'string'},
                'document_token': {'type': 'string'},
                'binary_data': {
                    'type': 'string',
                    'media': {
                        'binaryEncoding': 'base64',
                        },
                    },
                }
            }

    @classmethod
    def _token_upload_documents_output_schema(cls):
        return {'type': 'string'}

    @classmethod
    def _token_upload_documents_examples(cls):
        return [
            {
                'input': {
                    'document_token': '123',
                    'id': '12',
                    'filename': 'My doc.pdf',
                    'binary_data': 'Ym9uam91cgo='
                },
                'output': 'ok'
            }
        ]

    @classmethod
    def _token_upload_documents_convert_input(cls, parameters):
        DocumentRequestLine = Pool().get('document.request.line')
        parameters = cls._common_document_token_conversion(parameters)
        object_ = parameters['for_object']
        possible_lines = object_.get_documents_data()['document_request_lines']
        try:
            line = DocumentRequestLine(int(parameters['id']))
        except AccessError:
            raise APIInputError([{'type': 'wrong_document_request_id'}])

        if line not in possible_lines:
            raise APIInputError([{
                    'type': 'No matching document requests.',
                    'data': parameters['id']}])
        parameters['binary_data'] = base64.b64decode(parameters['binary_data'])
        parameters['request_line'] = line
        return parameters

    """*** End Upload Documents API Methods ***"""

    """↓↓↓↓ Start Submit Document Form API Methods ↓↓↓↓"""

    @classmethod
    def token_submit_document_answers(cls, parameters):
        pool = Pool()
        Core = pool.get('api.core')
        DocumentRequestLine = pool.get('document.request.line')
        object_ = parameters['for_object']
        possible_lines = object_.get_documents_data()['document_request_lines']
        to_be_answered = DocumentRequestLine(parameters['id'])
        if to_be_answered not in possible_lines:
            raise APIInputError([{'type': 'Wrong document request ids.'}])
        extra_data = Core._extra_data_convert(parameters['answers'])
        to_be_answered.extra_data = extra_data
        to_be_answered.save()
        with Transaction().set_user(0):
            DocumentRequestLine._generate_template_documents(
                [to_be_answered])
        return 'ok'

    @classmethod
    def _token_submit_document_answers_schema(cls):
        return {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'id': {'type': 'integer'},
                'answers': EXTRA_DATA_VALUES_SCHEMA,
                'document_token': {'type': 'string'},
                'required': ['id', 'answers', 'document_token']
                }
            }

    @classmethod
    def _token_submit_document_answers_output_schema(cls):
        return {'type': 'string'}

    @classmethod
    def _token_submit_document_answers_examples(cls):
        return [
            {
                'input': {
                    'document_token': '123',
                    'id': 26,
                    'answers': {
                        'question_key_1': 'some value',
                        'question_key_2': 'other value',
                        },
                    },
                'output': 'ok'
            }
        ]

    @classmethod
    def _token_submit_document_answers_convert_input(cls, parameters):
        return cls._common_document_token_conversion(parameters)
    """*** End Submit Document Form API Methods ***"""

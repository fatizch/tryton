# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import base64
from trytond.modules.document_request.api import DocumentTokenMixin
from trytond.pool import Pool, PoolMeta
from trytond.rpc import RPC
from trytond.config import config

from trytond.modules.coog_core import utils
from trytond.modules.coog_core.api import CODED_OBJECT_SCHEMA
from trytond.modules.api import APIInputError


class ContractApi(DocumentTokenMixin, metaclass=PoolMeta):
    __name__ = 'contract'

    @classmethod
    def __setup__(cls):
        super(ContractApi, cls).__setup__()
        if config.getboolean('env', 'testing') is True:
            cls.__rpc__.update({
                    'generate_required_documents_tokens':
                    RPC(readonly=False, instantiate=0),
                    })

    def generate_required_documents_tokens(self):
        parties = set()
        to_generate = set()

        # If the subscriber has requests lines
        # both as a susbscriber and as a covered party
        # we want to generate only one document token
        # for her, at the contract level
        def priority(line):
            if line.for_object.__name__ == 'contract':
                return 1
            return 2

        for request_line in sorted(self.document_request_lines,
                key=priority):
            if not request_line.received:
                contact = request_line.for_object.get_contact()
                if not contact:
                    continue
                if contact not in parties:
                    to_generate.add(request_line.for_object)
                parties.add(contact)
        for obj in to_generate:
            obj.generate_document_token()

    def retrieve_party_document_request_lines(self, party):
        pool = Pool()
        DocumentRequestLine = pool.get('document.request.line')
        return DocumentRequestLine.search(
            ['OR',
                ('for_object', '=', str(self)),
                [
                    ('for_object.party', 'in',
                        (party, None), 'contract.covered_element'),
                    ('for_object.contract', '=', self,
                        'contract.covered_element'),
                ]
            ])


class CoveredElementApi(DocumentTokenMixin, metaclass=PoolMeta):
    __name__ = 'contract.covered_element'

    def retrieve_party_document_request_lines(self, party):
        pool = Pool()
        DocumentRequestLine = pool.get('document.request.line')
        return DocumentRequestLine.search(
            [('for_object', '=', str(self))])


class APIParty(metaclass=PoolMeta):
    __name__ = 'api.party'

    @classmethod
    def _build_token_document_requests_response(cls, parameters):
        response = super()._build_token_document_requests_response(parameters)
        object_ = parameters['for_object']
        if object_.__name__ == 'contract':
            contract = object_
        elif object_.__name__ == 'contract.covered_element':
            contract = object_.contract
        else:
            return response
        product_name = cls.get_product_name(contract)
        response['party_data'].update(
            {'contract': {
                    'id': contract.id,
                    'product': product_name,
                    'quote_number': contract.quote_number,
                    'contract_number': contract.contract_number or '',
                    }
                }
            )
        return response

    @classmethod
    def get_product_name(cls, contract):
        return contract.product.name


class APIContract(metaclass=PoolMeta):
    __name__ = 'api.contract'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._apis.update({
                'b2b_upload_document': {
                    'public': False,
                    'readonly': False,
                    'description': 'Attach documents to a contract. Optionally,'
                    'the attachment can be linked to a document request line.',
                    },
                },
            )

    @classmethod
    def _b2b_upload_document_examples(cls):
        return [
            {
                'input': {
                    'contract': {'contract_number': '12'},
                    'answer_request': 'false',
                    'filename': 'toto.pdf',
                    'data': 'Ym9uam91cgo='
                },
                'output': 'ok'
            },
            {
                'input': {
                    'contract': {'id': '12'},
                    'answer_request': 'true',
                    'document_description': {'code': 'paper'},
                    'filename': 'toto.pdf',
                    'data': 'Ym9uam91cgo='
                },
                'output': 'ok'
            },
            {
                'input': {
                    'contract': {'quote_number': '12'},
                    'covered': {'code': '12'},
                    'answer_request': 'true',
                    'document_description': {'code': 'paper'},
                    'filename': 'toto.pdf',
                    'data': 'Ym9uam91cgo='
                },
                'output': 'ok'
            }
        ]

    @classmethod
    def _b2b_upload_document_contract_schema(cls):
        return {
            'anyOf': [
                {
                    'type': 'object',
                    'additionalProperties': False,
                    'properties': {'id': {"type": "string"}},
                    'required': ['id'],
                    },
                {
                    'type': 'object',
                    'additionalProperties': False,
                    'properties': {
                        'contract_number': {"type": "string"}},
                    'required': ['contract_number'],
                    },
                {
                    'type': 'object',
                    'additionalProperties': False,
                    'properties': {
                        'quote_number': {"type": "string"}},
                    'required': ['quote_number'],
                    },
                ],
            }

    @classmethod
    def _b2b_upload_document_schema(cls):
        contract_schema = cls._b2b_upload_document_contract_schema()
        return {
            'oneOf': [
                    {
                        'type': 'object',
                        'additionalProperties': False,
                        'properties': {
                            'contract': contract_schema,
                            'answer_request': {'const': 'false'},
                            'data': {'type': 'string'},
                            'filename': {'type': 'string'},
                        },
                        'required': ['contract', 'answer_request', 'data',
                        'filename'],
                    },
                    {
                        'type': 'object',
                        'additionalProperties': False,
                        'properties': {
                            'contract': contract_schema,
                            'answer_request': {'const': 'true'},
                            'document_description': CODED_OBJECT_SCHEMA,
                            'data': {'type': 'string'},
                            'filename': {'type': 'string'},
                            },
                        'required': ['contract', 'answer_request', 'data',
                            'document_description', 'filename'],
                    },
                    {
                        'type': 'object',
                        'additionalProperties': False,
                        'properties': {
                            'contract': contract_schema,
                            'covered': CODED_OBJECT_SCHEMA,
                            'answer_request': {'const': 'true'},
                            'document_description': CODED_OBJECT_SCHEMA,
                            'data': {'type': 'string'},
                            'filename': {'type': 'string'},
                            },
                        'required': ['contract', 'answer_request', 'data',
                            'document_description', 'covered', 'filename'],
                    },
            ]
        }

    @classmethod
    def _b2b_upload_document_output_schema(cls):
        return {'type': 'string'}

    @classmethod
    def b2b_upload_document(cls, parameters):
        pool = Pool()
        Attachment = pool.get('ir.attachment')
        contract = parameters['contract']

        # The Api User must be in the groups
        # of the document_desc if any
        attachment = Attachment(
            resource=contract,
            document_desc=parameters.get('document_description'),
            status='valid',
            name=parameters['filename'],
            data=parameters['data'])
        attachment.save()
        line = parameters.get('line')
        if line:
            line.attachment = attachment
            line.first_reception_date = utils.today()
            line.reception_date = utils.today()
            line.save()
        return 'ok'

    @classmethod
    def _b2b_upload_document_convert_input(cls, parameters):
        pool = Pool()
        API = pool.get('api')
        Contract = pool.get('contract')
        DocumentRequestLine = pool.get('document.request.line')
        CoveredElement = pool.get('contract.covered_element')
        base_parameters = parameters.copy()

        parameters['answer_request'] = {
            'true': True,
            'false': False
            }[parameters['answer_request']]

        (field_, value), = tuple(parameters['contract'].items())
        contract = Contract.search([(field_, '=', value)])
        if len(contract) != 1:
            raise APIInputError([{'type': 'Wrong contract identifier',
                    'data': parameters['contract']}])
        contract = contract[0]
        parameters['contract'] = contract

        for k, model_ in (('covered', 'party.party'),
                ('document_description', 'document.description')):
            value = parameters.get(k)
            if not value:
                continue
            instance = API.instantiate_code_object(
                model_, value)
            if k == 'covered':
                instance = CoveredElement.search([
                        ('contract', '=', contract),
                        ('party', '=', instance),
                        ])
                if len(instance) != 1:
                    raise APIInputError([{'type':
                                'Wrong contract/covered identifier',
                            'data': base_parameters}])
                instance = instance[0]
            parameters[k] = instance

        if parameters['answer_request'] is True:
            # The Api User must be in the groups
            # of the document_desc if any
            line_domain = [('contract', '=', contract),
                ('document_desc', '=',
                    parameters['document_description'])]
            covered = parameters.get('covered')
            if covered:
                line_domain.append(('for_object', '=', str(covered)))
            else:
                line_domain.append(('for_object', '=', str(contract)))
            request_line = DocumentRequestLine.search(line_domain)
            if len(request_line) != 1:
                raise APIInputError([
                        {'type':
                            'Wrong contract/covered/document_description '
                            'identifiers',
                        'data': base_parameters}])
            parameters['line'] = request_line[0]

        parameters['data'] = base64.b64decode(parameters['data'])

        return parameters

# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.modules.document_request.api import DocumentTokenMixin
from trytond.pool import Pool, PoolMeta
from trytond.rpc import RPC
from trytond.config import config


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

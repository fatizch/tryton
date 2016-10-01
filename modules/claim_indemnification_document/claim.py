# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool, PoolMeta
from trytond.model import ModelView

from trytond.modules.coog_core import fields

__all__ = [
    'Claim',
    'ClaimIndemnification',
    ]


class Claim:
    __metaclass__ = PoolMeta
    __name__ = 'claim'

    required_indemnification_docs = fields.Function(
        fields.One2Many('document.request.line', None, 'Required Docs'),
        'get_required_indemnification_docs')

    def get_required_indemnification_docs(self, name=None):
        if not self.indemnifications_to_schedule:
            return []
        requests = []
        for request in self.document_request_lines:
            if request.for_object in self.indemnifications_to_schedule:
                requests.append(request.id)
        return requests


class ClaimIndemnification:
    __metaclass__ = PoolMeta
    __name__ = 'claim.indemnification'

    document_request_lines = fields.One2Many('document.request.line',
        'for_object', 'Documents', delete_missing=True)

    @classmethod
    def __setup__(cls):
        super(ClaimIndemnification, cls).__setup__()
        cls._error_messages.update({
                'required_document': 'The document "%s" is required',
                })

    @classmethod
    def get_missing_documents(cls, indemnifications):
        DocumentRequests = Pool().get('document.request.line')
        claims = set([i.service.claim for i in indemnifications])
        document_requests = DocumentRequests.search([
                ('blocking', '=', True),
                ('received', '=', False),
                ('for_object', 'in',
                    [str(i) for i in indemnifications + list(claims)]),
                ])
        return document_requests

    @classmethod
    def check_required_documents(cls, indemnifications):
        missing_documents = cls.get_missing_documents(indemnifications)
        for doc in missing_documents:
            cls.append_functional_error(
                'required_document', doc.document_desc.name)

    def create_required_documents(self, required_documents):
        pool = Pool()
        DocumentDesc = pool.get('document.description')
        DocumentRequestLine = pool.get('document.request.line')
        if not required_documents:
            return
        documents = DocumentDesc.search([
                ('code', 'in', required_documents.keys())
                ])
        requests = []
        already_created = [d.document_desc
            for d in self.document_request_lines]
        for document in documents:
            if document in already_created:
                continue
            request = DocumentRequestLine(
                document_desc=document,
                for_object=self,
                claim=self.service.claim)
            for k, v in required_documents[document.code].iteritems():
                setattr(request, k, v)
            requests.append(request)
        DocumentRequestLine.save(requests)

    @classmethod
    def calculate_required_documents(cls, indemnifications):
        for indemnification in indemnifications:
            args = {}
            indemnification.init_dict_for_rule_engine(args)
            args['date'] = indemnification.service.loss.start_date
            required_documents = indemnification.service.benefit.\
                calculate_required_docs_for_indemnification(args)
            indemnification.create_required_documents(required_documents)

    @classmethod
    def check_schedulability(cls, indemnifications):
        super(ClaimIndemnification, cls).check_schedulability(indemnifications)
        cls.check_required_documents(indemnifications)

    @classmethod
    @ModelView.button
    def calculate(cls, indemnifications):
        super(ClaimIndemnification, cls).calculate(indemnifications)
        cls.calculate_required_documents(indemnifications)

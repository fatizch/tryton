from trytond.pool import Pool, PoolMeta

from trytond.modules.cog_utils import fields

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

    @fields.depends('document_request_lines')
    def on_change_with_doc_received(self, name=None):
        for doc in self.document_request_lines:
            if (doc.for_object and
                    doc.for_object.__name__ != 'claim.indemnification' and
                    not doc.received and doc.blocking):
                return False
        return True

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
        documents = DocumentDesc.search([
                ('code', 'in', required_documents.keys())
                ])
        requests = []
        for document in documents:
            request = DocumentRequestLine(
                document_desc=document,
                for_object=self,
                claim=self.service.claim)
            for k, v in required_documents[document.code].iteritems():
                setattr(request, k, v)
            requests.append(request)
        DocumentRequestLine.save(requests)
        return requests

    @classmethod
    def check_schedulability(cls, indemnifications):
        super(ClaimIndemnification, cls).check_schedulability(indemnifications)
        cls.check_required_documents(indemnifications)

from trytond.pool import Pool, PoolMeta

from trytond.model import ModelView

from trytond.modules.cog_utils import fields, model

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
            if (doc.for_object.__name__ != 'claim.indemnification' and
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
                'required_documents': 'The following documents '
                'are required before you can schedule this indemnification:\n'
                '%s'
                })

    @classmethod
    def check_required_documents(cls, indemnifications):
        DocumentRequests = Pool().get('document.request.line')
        missing_documents = []
        document_requests = DocumentRequests.search([
                ('for_object', 'in', [
                    str(i) for i in indemnifications]),
                ])
        with model.error_manager():
            for doc in document_requests:
                if not doc.received:
                    missing_documents.append(doc)
        return missing_documents

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
    @ModelView.button
    def schedule(cls, indemnifications):
        missing_docs = cls.check_required_documents(indemnifications)
        if missing_docs:
            missing_str = '\n'.join(
                ['- ' + doc.document_desc.name for doc in missing_docs])
            cls.raise_user_error('required_documents', missing_str)
        return super(ClaimIndemnification, cls).schedule(indemnifications)

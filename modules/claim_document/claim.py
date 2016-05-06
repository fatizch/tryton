from collections import defaultdict

from trytond.pool import PoolMeta, Pool
from trytond.model import ModelView

from trytond.modules.cog_utils import fields


__metaclass__ = PoolMeta
__all__ = [
    'Claim',
    ]


class Claim:
    __name__ = 'claim'

    document_request_lines = fields.One2Many('document.request.line',
        'for_object', 'Required Documents', delete_missing=True)
    document_request = fields.One2Many('document.request', 'needed_by',
        'Document Request')
    doc_received = fields.Function(
        fields.Boolean('All Documents Received',
            depends=['document_request_lines']),
        'on_change_with_doc_received')
    attachments = fields.One2Many('ir.attachment', 'resource', 'Attachments',
        target_not_required=True)

    @classmethod
    def __setup__(cls):
        super(Claim, cls).__setup__()
        cls._buttons.update({
                'button_generate_document_request': {},
                })

    @fields.depends('document_request_lines')
    def on_change_with_doc_received(self, name=None):
        for doc in self.document_request_lines:
            if not doc.received:
                return False
        return True

    @classmethod
    @ModelView.button
    def button_generate_document_request(cls, claims):
        pool = Pool()
        DocumentRequest = pool.get('document.request')
        for claim in claims:
            DocumentRequest.create_request(claim,
                [line for line in claim.document_request_lines
                    if not line.received])

    def link_attachments_to_requests(self):
        Request = Pool().get('document.request')
        attachments_grouped = defaultdict(list)
        for attachment in self.attachments:
            attachments_grouped[attachment.document_desc].append(attachment)
        to_save = []
        for request in self.document_request_lines:
            if not (request.document_desc and
                    len(attachments_grouped[request.document_desc]) == 1):
                continue
            request.attachment = attachments_grouped[request.document_desc][0]
            request.reception_date = request.attachment.create_date.date()
            to_save.append(request)
        Request.save(to_save)

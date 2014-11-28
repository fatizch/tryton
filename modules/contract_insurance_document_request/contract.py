from collections import defaultdict

from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval

from trytond.modules.cog_utils import fields

__all__ = [
    'Contract',
    ]

__metaclass__ = PoolMeta


class Contract:
    __name__ = 'contract'

    attachments = fields.One2Many('ir.attachment', 'resource', 'Attachments')
    doc_received = fields.Function(
        fields.Boolean('All Document Received',
            depends=['document_request_lines']),
        'on_change_with_doc_received')
    document_request_lines = fields.One2Many('document.request.line',
        'for_object', 'Documents',
        states={'readonly': Eval('status') != 'quote'},
        depends=['status'])

    @fields.depends('document_request_lines')
    def on_change_with_doc_received(self, name=None):
        if not self.document_request_lines:
            return False
        for doc in self.document_request_lines:
            if not doc.received:
                return False
        return True

    def init_subscription_document_request(self):
        pool = Pool()
        DocumentRequestLine = pool.get('document.request.line')
        documents = []
        product_docs, errs = self.product.get_result(
            'documents', {
                'contract': self,
                'date': self.start_date,
                'appliable_conditions_date': self.appliable_conditions_date})
        if errs:
            return False, errs
        if product_docs:
            documents.extend(product_docs)
        for option in self.options:
            if not option.status == 'active':
                continue
            option_docs, errs = option.coverage.get_result(
                'documents', {
                    'contract': self,
                    'option': option.coverage.code,
                    'appliable_conditions_date':
                    self.appliable_conditions_date,
                    'date': self.start_date})
            if errs:
                return False, errs
            if not option_docs:
                continue
            documents.extend(option_docs)
        for elem in self.covered_elements:
            for option in elem.options:
                if not option.status == 'active':
                    continue
                sub_docs, errs = option.coverage.get_result(
                    'documents', {
                        'contract': self,
                        'option': option.coverage.code,
                        'date': self.start_date,
                        'appliable_conditions_date':
                        self.appliable_conditions_date,
                        'kind': 'sub',
                        'sub_elem': elem})
                if errs:
                    return False, errs
                if not sub_docs:
                    continue
                documents.extend(sub_docs)
        existing_document_desc = [request.document_desc
            for request in self.document_request_lines]
        for desc in documents:
            if desc in existing_document_desc:
                existing_document_desc.remove(desc)
                continue
            line = DocumentRequestLine()
            line.document_desc = desc
            line.for_object = '%s,%s' % (self.__name__, self.id)
            line.save()
        to_delete = []
        for request in self.document_request_lines:
            if (request.document_desc in existing_document_desc and
                    not request.send_date and not request.reception_date):
                to_delete.append(request)
        DocumentRequestLine.delete(to_delete)

    def link_attachments_to_requests(self):
        attachments_grouped = defaultdict(list)
        for attachment in self.attachments:
            attachments_grouped[attachment.document_desc].append(attachment)
        for request in self.document_request_lines:
            if not (request.document_desc and
                    len(attachments_grouped[request.document_desc]) == 1):
                continue
            request.attachment = attachments_grouped[request.document_desc][0]
            request.save()

    @classmethod
    def update_contract_after_import(cls, contracts):
        super(Contract, cls).update_contract_after_import(contracts)
        for contract in contracts:
            contract.init_subscription_document_request()
            contract.link_attachments_to_requests()

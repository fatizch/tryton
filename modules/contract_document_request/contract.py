from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval

from trytond.modules.cog_utils import fields

__all__ = [
    'Contract',
    ]

__metaclass__ = PoolMeta


class Contract:
    __name__ = 'contract'

    doc_received = fields.Function(
        fields.Boolean('All Document Received', depends=['documents']),
        'on_change_with_doc_received')
    documents = fields.One2Many('document.request', 'needed_by', 'Documents',
        states={'readonly': Eval('status') != 'quote'},
        depends=['status'], size=1)

    @fields.depends('documents')
    def on_change_with_doc_received(self, name=None):
        if not self.documents:
            return False
        for doc in self.documents:
            if not doc.is_complete:
                return False
        return True

    def init_subscription_document_request(self):
        DocRequest = Pool().get('document.request')
        if not (hasattr(self, 'documents') and self.documents):
            good_req = DocRequest()
            good_req.needed_by = self
            good_req.save()
        else:
            good_req = self.documents[0]
        documents = []
        product_docs, errs = self.product.get_result(
            'documents', {
                'contract': self,
                'date': self.start_date,
                'appliable_conditions_date': self.appliable_conditions_date})
        if errs:
            return False, errs
        if product_docs:
            documents.extend([(doc_desc, self) for doc_desc in product_docs])
        for option in self.options:
            if not option.status == 'active':
                continue
            option_docs, errs = self.product.get_result(
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
            documents.extend([(doc_desc, self) for doc_desc in option_docs])
        for elem in self.covered_elements:
            for option in elem.options:
                if not option.status == 'active':
                    continue
                sub_docs, errs = self.product.get_result(
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
                documents.extend([(doc_desc, elem) for doc_desc in sub_docs])
        good_req.add_documents(self.start_date, documents)
        good_req.clean_extras(documents)
        return True, ()

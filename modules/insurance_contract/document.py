import copy
from trytond.pool import PoolMeta

__all__ = [
    'Document',
    'DocumentRequest',
    'RequestFinder',
]


class DocumentRequest():
    'Document Request'

    __name__ = 'ins_product.document_request'
    __metaclass__ = PoolMeta

    @classmethod
    def __setup__(cls):
        super(DocumentRequest, cls).__setup__()
        cls.needed_by = copy.copy(cls.needed_by)
        cls.needed_by.selection.append(
            ('ins_contract.contract', 'Contract'))


class Document():
    'Document'

    __name__ = 'ins_product.document'
    __metaclass__ = PoolMeta

    @classmethod
    def __setup__(cls):
        super(Document, cls).__setup__()
        cls.for_object = copy.copy(cls.for_object)
        cls.for_object.selection.append(
            ('ins_contract.contract', 'Contract'))
        cls.for_object.selection.append(
            ('ins_contract.option', 'Option'))
        cls.for_object.selection.append(
            ('ins_contract.covered_element', 'Covered Element'))


class RequestFinder():
    'Request Finder'

    __name__ = 'ins_product.request_finder'
    __metaclass__ = PoolMeta

    @classmethod
    def allowed_values(cls):
        result = super(RequestFinder, cls).allowed_values()
        result.update({
            'ins_contract.contract': (
                'Contract', 'contract_number')})
        return result

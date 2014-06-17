from trytond.pool import PoolMeta


__metaclass__ = PoolMeta
__all__ = [
    'DocumentRequest',
    'Document',
    'RequestFinder',
    ]


class DocumentRequest:
    __name__ = 'document.request'

    @classmethod
    def __setup__(cls):
        super(DocumentRequest, cls).__setup__()
        cls.needed_by.selection.append(('claim', 'Claim'))
        cls.needed_by.selection.append(
            ('contract.service', 'Delivered Service'))


class Document:
    __name__ = 'document.request.line'

    @classmethod
    def __setup__(cls):
        super(Document, cls).__setup__()
        cls.for_object.selection.append(('claim', 'Claim'))
        cls.for_object.selection.append(
            ('contract.service', 'Delivered Service'))


class RequestFinder:
    __name__ = 'document.receive.request'

    @classmethod
    def allowed_values(cls):
        result = super(RequestFinder, cls).allowed_values()
        result.update({'claim': ('Claim', 'name')})
        return result

from trytond.pool import PoolMeta

__metaclass__ = PoolMeta
__all__ = [
    'DocumentRequest',
    'DocumentReceiveRequest',
    ]


class DocumentRequest:
    __name__ = 'document.request'

    @classmethod
    def __setup__(cls):
        super(DocumentRequest, cls).__setup__()
        cls.needed_by.selection.append(
            ('contract', 'Contract'))


class DocumentReceiveRequest:
    __name__ = 'document.receive.request'

    @classmethod
    def allowed_values(cls):
        result = super(DocumentReceiveRequest, cls).allowed_values()
        result.update({'contract': ('Contract', 'contract_number')})
        return result

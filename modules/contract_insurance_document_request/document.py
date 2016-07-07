# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta


__all__ = [
    'DocumentRequest',
    'DocumentReceiveRequest',
    ]


class DocumentRequest:
    __metaclass__ = PoolMeta
    __name__ = 'document.request'

    @classmethod
    def __setup__(cls):
        super(DocumentRequest, cls).__setup__()
        cls.needed_by.selection.append(
            ('contract', 'Contract'))


class DocumentReceiveRequest:
    __metaclass__ = PoolMeta
    __name__ = 'document.receive.request'

    @classmethod
    def allowed_values(cls):
        result = super(DocumentReceiveRequest, cls).allowed_values()
        result.update({'contract': ('Contract', 'contract_number')})
        return result

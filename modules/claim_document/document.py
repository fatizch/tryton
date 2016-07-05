# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta


__metaclass__ = PoolMeta
__all__ = [
    'DocumentRequest',
    'RequestFinder',
    ]


class DocumentRequest:
    __name__ = 'document.request'

    @classmethod
    def __setup__(cls):
        super(DocumentRequest, cls).__setup__()
        cls.needed_by.selection.append(('claim', 'Claim'))
        cls.needed_by.selection.append(
            ('claim.service', 'Claim Service'))


class RequestFinder:
    __name__ = 'document.receive.request'

    @classmethod
    def allowed_values(cls):
        result = super(RequestFinder, cls).allowed_values()
        result.update({'claim': ('Claim', 'name')})
        return result

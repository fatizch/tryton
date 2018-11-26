# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool, PoolMeta

__all__ = [
    'Claim',
    ]


class Claim(metaclass=PoolMeta):
    __name__ = 'claim'

    def init_declaration_document_request(self):
        DocumentRequestLine = Pool().get('document.request.line')
        super(Claim, self).init_declaration_document_request()
        DocumentRequestLine.update_electronic_signature_status(
            self.document_request_lines)

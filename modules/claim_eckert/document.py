# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool


__all__ = [
    'DocumentRequestLine',
    ]


class DocumentRequestLine:
    __metaclass__ = PoolMeta
    __name__ = 'document.request.line'

    @classmethod
    def __setup__(cls):
        super(DocumentRequestLine, cls).__setup__()
        cls._error_messages.update({
                'not_synced_beneficiary_requests': 'Documents must be '
                'requested together for beneficiary %(beneficiary)s',
                })

    @classmethod
    def validate(cls, requests):
        super(DocumentRequestLine, cls).validate(requests)
        for request in requests:
            request.check_beneficiary_dates()

    def check_beneficiary_dates(self):
        if not isinstance(self.for_object, Pool().get('claim.beneficiary')):
            return
        if not self.for_object.is_eckert:
            return
        if not self.blocking:
            return
        if not all(x.request_date == self.request_date
                for x in self.for_object.document_request_lines if x.blocking):
            self.raise_user_error('not_synced_beneficiary_requests',
                {'beneficiary': self.for_object.party.rec_name})

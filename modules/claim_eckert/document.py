# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.i18n import gettext
from trytond.model.exceptions import ValidationError
from trytond.pool import PoolMeta, Pool


__all__ = [
    'DocumentRequestLine',
    ]


class DocumentRequestLine(metaclass=PoolMeta):
    __name__ = 'document.request.line'

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
            raise ValidationError(gettext(
                    'claim_eckert.msg_not_synced_beneficiary_requests',
                    beneficiary=self.for_object.party.rec_name))

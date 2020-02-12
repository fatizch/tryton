# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

from trytond.modules.coog_core import fields

__all__ = [
    'Attachment',
    ]


class Attachment(metaclass=PoolMeta):
    __name__ = 'ir.attachment'

    @fields.depends('signature')
    def is_signed(self):
        return self.signature.status == 'completed' if self.signature else False

    @fields.depends('document_desc')
    def on_change_with_can_see_signatures(self, name=None):
        return super(Attachment, self
            ).on_change_with_can_see_signatures(
            name) and (self.document_desc
            and self.document_desc.digital_signature_required)

    def get_signature_credential_and_config(self):
        if not self.document_desc:
            return super(Attachment, self).get_signature_credential_and_config()
        return (self.document_desc.signature_credential,
            self.document_desc.signature_configuration)

    def get_party(self, report=None):
        party = super(Attachment, self).get_party(report)
        if party:
            return party
        if getattr(self, 'request_line', None):
            return self.request_line.get_contact()
        if report:
            return (report.get('party') or report.get('origin')
                or report.get('resource')).get_contact()
        return self.resource.get_contact()

    def get_struct_for_signature(self, report=None):
        report = super(Attachment, self).get_struct_for_signature(report)
        if not report or not self.document_desc:
            return report
        return self.document_desc.get_coordinates(report)

# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool, PoolMeta

__all__ = [
    'ReportTemplate',
    ]


class ReportTemplate:
    __metaclass__ = PoolMeta
    __name__ = 'report.template'

    def _create_attachment_from_report(self, report):
        attachment = super(ReportTemplate, self)._create_attachment_from_report(
            report)
        if attachment.document_desc and \
                attachment.document_desc.digital_signature_required:
            signer = report.get('party') or (report.get('origin') or
                    report.get('resource')).get_contact()
            attachment.update_electronic_signer(signer)
        return attachment

    def save_reports_in_edm(self, reports):
        Attachment = Pool().get('ir.attachment')
        attachments = super(ReportTemplate, self).save_reports_in_edm(reports)
        to_request_for_signature = []
        for attachment in attachments:
            if attachment.document_desc and \
                    attachment.document_desc.digital_signature_required:
                if not attachment.has_signature_transaction_request():
                    to_request_for_signature.append(attachment)
        if to_request_for_signature:
            Attachment.request_electronic_signature_transaction(
                to_request_for_signature)
        return attachments

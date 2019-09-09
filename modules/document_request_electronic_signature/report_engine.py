# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool, PoolMeta

__all__ = [
    'ReportTemplate',
    ]


class ReportTemplate(metaclass=PoolMeta):
    __name__ = 'report.template'

    def produce_reports(self, objects, context_=None):
        Signature = Pool().get('document.signature')
        reports, attachments = super(ReportTemplate, self).produce_reports(
            objects, context_)
        if (not self.document_desc
                or not self.document_desc.digital_signature_required):
            return reports, attachments
        for report, attachment in zip(reports,
                attachments or [None] * len(reports)):
            signer = (report.get('party') or (report.get('origin')
                    or report.get('resource')
                    or attachment.resource).get_contact())
            # No need to try an electronic signature if we can't go through
            if signer and signer.email and (signer.mobile or signer.phone):
                report['signers'] = [signer]
                Signature.request_transaction(report, attachment,
                    config=self.document_desc.signature_configuration
                    if self.document_desc else None,
                    extra_data=self.document_desc.extra_data
                    if self.document_desc else None,
                    credential=self.document_desc.signature_credential
                    if self.document_desc else None)

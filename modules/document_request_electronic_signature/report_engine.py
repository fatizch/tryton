# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

__all__ = [
    'ReportTemplate',
    ]


class ReportTemplate(metaclass=PoolMeta):
    __name__ = 'report.template'

    def produce_reports(self, objects, context_=None, doc_desc=None):
        reports, attachments = super(ReportTemplate, self).produce_reports(
            objects, context_, doc_desc)
        if doc_desc and doc_desc.digital_signature_required:
            for report, attachment in zip(reports,
                    attachments or [None] * len(reports)):
                if not attachment:
                    continue
                attachment.create_new_signature(report, report.get('origin'),
                    credential=doc_desc.signature_credential if doc_desc
                    else None,
                    config=doc_desc.signature_configuration if doc_desc
                    else None)
        return reports, attachments

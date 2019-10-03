# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

__all__ = [
    'ReportTemplate',
    ]


class ReportTemplate(metaclass=PoolMeta):
    __name__ = 'report.template'

    def produce_reports(self, objects, context_=None):
        reports, attachments = super(ReportTemplate, self).produce_reports(
            objects, context_)
        if (not self.document_desc
                or not self.document_desc.digital_signature_required):
            return reports, attachments
        for report, attachment in zip(reports,
                attachments or [None] * len(reports)):
            self.document_desc.init_signature(report, attachment,
                from_object=report.get('origin'))

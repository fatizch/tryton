# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import report_engine


def register():
    Pool.register(
        report_engine.ReportTemplate,
        report_engine.TemplateTemplateRelation,
        report_engine.ReportCreateSelectTemplate,
        report_engine.ImageAttachment,
        report_engine.ReportTemplateImageAttachmentRelation,
        module='report_engine_email', type_='model')

    Pool.register(
        report_engine.ReportCreate,
        module='report_engine_email', type_='wizard')

    Pool.register(
        report_engine.ReportGenerate,
        report_engine.ReportGenerateEmail,
        module='report_engine_email', type_='report')

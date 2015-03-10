from trytond.pool import Pool

from .report_engine import *
from .offered import *


def register():
    Pool.register(
        ReportTemplate,
        ReportTemplateOffered,
        ReportProductRelation,
        ReportTemplateVersion,
        ReportCreateSelectTemplate,
        ReportCreatePreview,
        ReportCreatePreviewLine,
        ReportCreateAttach,
        module='report_engine', type_='model')
    Pool.register(
        ReportGenerate,
        ReportGenerateFromFile,
        module='report_engine', type_='report')
    Pool.register(
        ReportCreate,
        module='report_engine', type_='wizard')

from trytond.pool import Pool

from .report_engine import *
from .ir import *


def register():
    Pool.register(
        ReportTemplate,
        ReportTemplateVersion,
        ReportCreateSelectTemplate,
        ReportCreatePreview,
        ReportCreatePreviewLine,
        ReportCreateAttach,
        Model,
        module='report_engine', type_='model')
    Pool.register(
        ReportGenerate,
        ReportGenerateFromFile,
        module='report_engine', type_='report')
    Pool.register(
        ReportCreate,
        module='report_engine', type_='wizard')

from trytond.pool import Pool

from .report_engine import *
from .ir import *
from .event import *
from .tools import *


def register():
    Pool.register(
        ReportTemplate,
        ReportTemplateVersion,
        ReportCreateSelectTemplate,
        ReportCreatePreview,
        ReportCreatePreviewLine,
        ReportCreateAttach,
        EventTypeAction,
        EventTypeActionReportTemplate,
        Model,
        SelectTemplatesForConversion,
        MatchDisplayer,
        module='report_engine', type_='model')
    Pool.register(
        ReportGenerate,
        ReportGenerateFromFile,
        module='report_engine', type_='report')
    Pool.register(
        ReportCreate,
        ConvertTemplate,
        module='report_engine', type_='wizard')

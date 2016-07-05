# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from .report_engine import *
from .ir import *
from .event import *
from .tools import *
from .batch import *


def register():
    Pool.register(
        ReportTemplate,
        TemplateParameter,
        TemplateTemplateParameterRelation,
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
        ReportProductionRequest,
        ConfirmReportProductionRequestTreat,
        ReportProductionRequestTreatResult,
        ReportProductionRequestTreatmentBatch,
        ReportInputParameters,
        module='report_engine', type_='model')

    Pool.register(
        ReportGenerate,
        ReportGenerateFromFile,
        module='report_engine', type_='report')

    Pool.register(
        ReportCreate,
        ConvertTemplate,
        TreatReportProductionRequest,
        module='report_engine', type_='wizard')

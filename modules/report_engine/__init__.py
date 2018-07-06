# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from report_engine import Printable  # NOQA

import report_engine
import ir
import event
import tools
import batch
import res
import party
import wizard


def register():
    Pool.register(
        report_engine.ReportTemplate,
        report_engine.ReportLightTemplate,
        report_engine.TemplateParameter,
        report_engine.TemplateTemplateParameterRelation,
        report_engine.ReportTemplateVersion,
        report_engine.ReportCreateSelectTemplate,
        report_engine.ReportCreatePreview,
        report_engine.ReportCreatePreviewLine,
        report_engine.ReportTemplateGroupRelation,
        event.EventTypeAction,
        event.EventTypeActionReportTemplate,
        event.ReportProductionRequest,
        event.ConfirmReportProductionRequestTreat,
        event.ReportProductionRequestTreatResult,
        ir.Model,
        tools.SelectTemplatesForConversion,
        tools.MatchDisplayer,
        batch.ReportProductionRequestTreatmentBatch,
        res.Group,
        party.Party,
        wizard.PrintUnboundReportStart,
        module='report_engine', type_='model')

    Pool.register(
        report_engine.CoogReport,
        report_engine.ReportGenerate,
        report_engine.ReportGenerateFromFile,
        module='report_engine', type_='report')

    Pool.register(
        report_engine.ReportCreate,
        tools.ConvertTemplate,
        event.TreatReportProductionRequest,
        wizard.PrintUnboundReport,
        module='report_engine', type_='wizard')

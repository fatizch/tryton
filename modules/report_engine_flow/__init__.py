from trytond.pool import Pool

from .report_engine import *


def register():
    Pool.register(
        ReportTemplate,
        FlowVariable,
        TemplateVariableRelation,
        module='report_engine_flow', type_='model')

    Pool.register(
        ReportCreate,
        module='report_engine_flow', type_='wizard')

    Pool.register(
        ReportGenerate,
        module='report_engine_flow', type_='report')

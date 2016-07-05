# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
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

# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
import report_engine


def register():
    Pool.register(
        report_engine.ReportTemplate,
        module='report_engine_primotexto', type_='model')

    Pool.register(
        report_engine.ReportGenerate,
        module='report_engine_primotexto', type_='report')

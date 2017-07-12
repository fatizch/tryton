# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import dunning
import report_engine


def register():
    Pool.register(
        report_engine.ReportTemplate,
        dunning.Dunning,
        dunning.Level,
        module='account_dunning_report_engine', type_='model')

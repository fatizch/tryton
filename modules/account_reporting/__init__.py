# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import wizard


def register():
    Pool.register(
        wizard.PrintMoveLineAggregatedReportStart,
        module='account_reporting', type_='model')

    Pool.register(
        wizard.PrintMoveLineAggregatedReport,
        module='account_reporting', type_='wizard')

    Pool.register(
        wizard.MoveLineAggregatedReport,
        module='account_reporting', type_='report')

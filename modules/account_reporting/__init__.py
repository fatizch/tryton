# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from .wizard import *


def register():
    Pool.register(
        PrintMoveLineAggregatedReportStart,
        module='account_reporting', type_='model')
    Pool.register(
        PrintMoveLineAggregatedReport,
        module='account_reporting', type_='wizard')
    Pool.register(
        MoveLineAggregatedReport,
        module='account_reporting', type_='report')

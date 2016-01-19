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

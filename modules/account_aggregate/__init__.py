# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .account import *
from .batch import *


def register():
    Pool.register(
        FiscalYear,
        Journal,
        Snapshot,
        Move,
        Line,
        Configuration,
        SnapshotStart,
        SnapshotDone,
        SnapshotTakeBatch,
        LineAggregated,
        ExtractAggregatedMove,
        module='account_aggregate', type_='model')
    Pool.register(
        TakeSnapshot,
        OpenLineAggregated,
        OpenLine,
        module='account_aggregate', type_='wizard')

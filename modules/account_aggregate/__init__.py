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
        module='account_aggregate', type_='model')
    Pool.register(
        TakeSnapshot,
        OpenLineAggregated,
        OpenLine,
        module='account_aggregate', type_='wizard')

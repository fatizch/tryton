from trytond.pool import Pool
from .account import *


def register():
    Pool.register(
        Journal,
        Snapshot,
        Move,
        Line,
        Configuration,
        SnapshotStart,
        SnapshotDone,
        LineAggregated,
        module='account_aggregate', type_='model')
    Pool.register(
        TakeSnapshot,
        OpenLineAggregated,
        OpenLine,
        module='account_aggregate', type_='wizard')

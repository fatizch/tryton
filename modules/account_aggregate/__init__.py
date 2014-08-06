from trytond.pool import Pool
from .account import *


def register():
    Pool.register(
        Move,
        SnapshotStart,
        SnapshotDone,
        LineAggregated,
        module='account_aggregate', type_='model')
    Pool.register(
        Snapshot,
        OpenLineAggregated,
        OpenLine,
        module='account_aggregate', type_='wizard')

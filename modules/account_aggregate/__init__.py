# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
import account
import batch


def register():
    Pool.register(
        account.FiscalYear,
        account.Journal,
        account.Snapshot,
        account.Move,
        account.Line,
        account.Configuration,
        account.ConfigurationSnapshotSequence,
        account.SnapshotStart,
        account.SnapshotDone,
        batch.SnapshotTakeBatch,
        account.LineAggregated,
        batch.ExtractAggregatedMove,
        module='account_aggregate', type_='model')
    Pool.register(
        account.TakeSnapshot,
        account.OpenLineAggregated,
        account.OpenLine,
        module='account_aggregate', type_='wizard')

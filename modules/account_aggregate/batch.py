# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging
import datetime
from decimal import Decimal

from trytond.pool import Pool
from trytond.modules.coog_core import batch
from trytond.transaction import Transaction
from trytond.server_context import ServerContext

from trytond.modules.coog_core import utils
from trytond.modules.report_engine_flow import batch as flow_batch

__all__ = [
    'SnapshotTakeBatch',
    'ExtractAggregatedMove',
    ]


class SnapshotTakeBatch(batch.BatchRootNoSelect):
    'Snapshot Moves Take batch'

    __name__ = 'account.move.snapshot.take'

    logger = logging.getLogger(__name__)

    @classmethod
    def execute(cls, objects, ids, output_folder=None):
        pool = Pool()
        Snapshot = pool.get('account.move.snapshot')
        snap_id = Snapshot.take_snapshot()
        cls.logger.info('snapshot %s taken' % snap_id)


class ExtractAggregatedMove(flow_batch.BaseMassFlowBatch):
    'Extract Aggregated Move'

    __name__ = 'account.move.aggregated.extract'

    @classmethod
    def get_batch_main_model_name(cls):
        return 'account.move.snapshot'

    @classmethod
    def sanitize(cls, value):
        if isinstance(value, datetime.date):
            return datetime.datetime.strftime(value, '%Y%m%d')
        elif isinstance(value, basestring):
            return value.encode('UTF-8')
        return value

    @classmethod
    def select_ids(cls, *args, **kwargs):
        cls.check_mandatory_parameters(*args, **kwargs)
        cursor = Transaction().connection.cursor()
        treatment_date = datetime.datetime.strftime(kwargs.get(
                'treatment_date'), '%Y-%m-%d')
        with ServerContext().set_context(
                snap_ref=kwargs.get('reference', None),
                batch_treatment_date=treatment_date):
            table_query = Pool().get('account.move.line.aggregated'
                ).table_query()

        cursor.execute(*table_query)
        return (tuple(rows) for rows in cursor.fetchall())

    @classmethod
    def check_mandatory_parameters(cls, *args, **kwargs):
        super(ExtractAggregatedMove, cls).check_mandatory_parameters(*args,
            **kwargs)
        assert kwargs.get('treatment_date'), 'treatment_date is required'

    @classmethod
    def object_fields_mapper(cls, *args, **kwargs):
        return [
            ('journal_code', lambda obj, *args: obj[3].code),
            ('date', lambda obj, *args: obj[6]),
            ('aggregated', lambda obj, *args: obj[4].replace('/', '')),
            ('bank_code', lambda obj, *args: obj[2].code),
            ('description', lambda obj, *args: obj[5]),
            ('debit', lambda obj, *args: obj[8].replace('.', ',')),
            ('credit', lambda obj, *args: obj[9].replace('.', ',')),
            ('move_direction', lambda obj, *args: obj[10]),
            ]

    @classmethod
    def transform_values(cls, values):
        pool = Pool()
        Journal = pool.get('account.journal')
        Account = pool.get('account.account')
        Snapshot = pool.get('account.move.snapshot')
        Line = Pool().get('account.move.line')

        lines = Line.browse([x[0] for x in values])
        descriptions = (x[5] for x in values)
        aggregated_ids = (x[6] for x in values)
        accounts = Account.browse([x[7] for x in values])
        journals = Journal.browse([x[8] for x in values])
        move_dates = (x[9] for x in values)
        post_dates = (x[10] for x in values)
        snapshots = Snapshot.browse(x[11] for x in values)
        debits = (x[12] for x in values)
        credits = (x[13] for x in values)
        directions_moves = ('C' if Decimal(x[13]) - Decimal(x[12]) > 0 else 'D'
            for x in values)
        return (snapshots, lines, accounts, journals, aggregated_ids,
            descriptions, move_dates, post_dates, debits, credits,
            directions_moves)

    @classmethod
    def parse_select_ids(cls, fetched_data, *args, **kwargs):
        for values in utils.iterator_slice(fetched_data,
                int(kwargs.get('flush_size'))):
            for single_values in zip(*cls.transform_values(values)):
                yield single_values

    @classmethod
    def execute(cls, objects, ids, *args, **kwargs):
        # We are not processing huge amount of data
        objects = list(objects)
        super(ExtractAggregatedMove, cls).execute(objects, ids, *args,
            **kwargs)
        Snapshot = Pool().get('account.move.snapshot')
        snapshots = [x[0] for x in objects if not x[0].extracted]
        Snapshot.write(snapshots, {'extracted': True})

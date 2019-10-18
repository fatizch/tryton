# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import os
import logging
import datetime
from decimal import Decimal
from itertools import groupby

from trytond.pool import Pool
from trytond.modules.coog_core import batch
from trytond.transaction import Transaction
from trytond.server_context import ServerContext
from trytond.exceptions import UserError
from trytond.i18n import gettext

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
    def __setup__(cls):
        super(SnapshotTakeBatch, cls).__setup__()
        cls._default_config_items.update({
                'job_size': 0,
                })

    @classmethod
    def get_batch_main_model_name(cls):
        return 'account.move.snapshot'

    @classmethod
    def parse_params(cls, params):
        params = super(SnapshotTakeBatch, cls).parse_params(params)
        assert params.get('job_size') == 0
        return params

    @classmethod
    def execute(cls, objects, ids):
        pool = Pool()
        Snapshot = pool.get('account.move.snapshot')
        snap_id = Snapshot.take_snapshot()
        cls.logger.info('snapshot %s taken' % snap_id)


class ExtractAggregatedMove(flow_batch.BaseMassFlowBatch):
    'Extract Aggregated Move'

    __name__ = 'account.move.aggregated.extract'

    @classmethod
    def __setup__(cls):
        super(ExtractAggregatedMove, cls).__setup__()
        cls._default_config_items.update({
                'job_size': 0,
                'flush_size': 1024,
                })

    @classmethod
    def get_batch_main_model_name(cls):
        return 'account.move.snapshot'

    @classmethod
    def sanitize(cls, value):
        if isinstance(value, datetime.date):
            return datetime.datetime.strftime(value, '%Y%m%d')
        return value

    @classmethod
    def get_header_value(cls, *args, **kwargs):
        return [
            gettext('account_aggregate.msg_journal_code'),
            gettext('account_aggregate.msg_date'),
            gettext('account_aggregate.msg_aggregated'),
            gettext('account_aggregate.msg_bank_code'),
            gettext('account_aggregate.msg_description'),
            gettext('account_aggregate.msg_debit'),
            gettext('account_aggregate.msg_credit'),
            gettext('account_aggregate.msg_move_direction'),
            ]

    @classmethod
    def select_ids(cls, *args, **kwargs):
        with_header = Pool().get('account.configuration')(
            1).header_in_aggregate_move_file
        if with_header and ServerContext().get(
                'job_size'):
            UserError(gettext(
                'account_aggregate.msg_multiple_running_processes'))
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
        for snap, rows in groupby((rows for rows in cursor.fetchall()),
                lambda x: x[11]):
            yield tuple(rows)

    @classmethod
    def check_mandatory_parameters(cls, *args, **kwargs):
        assert kwargs.get('treatment_date'), 'treatment_date is required'
        assert kwargs.get('output_dir'), 'output_dir is required'
        super(ExtractAggregatedMove, cls).check_mandatory_parameters(*args,
            **kwargs)

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
    def transform_values(cls, values, *args, **kwargs):
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
        for values in fetched_data:
            for single_values in zip(*cls.transform_values(
                        values, *args, **kwargs)):
                yield single_values

    @classmethod
    def get_filename(cls, *args, **kwargs):
        output_dir = kwargs.get('output_dir')
        filename = kwargs.get('output_filename')
        if not filename:
            treatment_date = kwargs.get('treatment_date')
            current_time = treatment_date.strftime('%Y-%m-%d')
            filename = 'snapshots_%s.txt' % current_time
        return os.path.join(output_dir, filename)

    @classmethod
    def execute(cls, objects, ids, *args, **kwargs):
        # We are not processing huge amount of data
        with_header = Pool().get('account.configuration')(
            1).header_in_aggregate_move_file
        # Check if there is only one process running
        # Extraction of header won't work if it wasn't the case
        if with_header and not ServerContext().get('job_size'):
            cls.write_header(*args, **kwargs)
        objects = list(objects)
        super(ExtractAggregatedMove, cls).execute(objects, ids, *args,
            **kwargs)
        Snapshot = Pool().get('account.move.snapshot')
        snapshots = {x[0] for x in objects if not x[0].extracted}
        if snapshots:
            Snapshot.write(list(snapshots), {'extracted': True})

# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging
import csv
import os

from trytond.pool import Pool
from trytond.modules.coog_core import batch, coog_string


__all__ = [
    'SnapshotTakeBatch',
    ]


class SnapshotTakeBatch(batch.BatchRootNoSelect):
    'Snapshot Moves Take batch'

    __name__ = 'account.move.snapshot.take'

    logger = logging.getLogger(__name__)

    @classmethod
    def sanitize_value(cls, value):
        if isinstance(value, basestring):
            return value.encode('utf-8')
        return value

    @classmethod
    def fields_to_export(cls):
        """
        List of tuple which the first element is the name of the column, and
        the second one, the associated value.
        """
        label = coog_string.translate_label
        return [
            ((lambda x: label(x.snapshot, 'name')), (lambda x:
                    x.snapshot.name)),
            ((lambda x: label(x, 'date')), (lambda x: x.date)),
            ((lambda x: label(x, 'journal')), (lambda x: x.journal.code)),
            ((lambda x: label(x, 'account')), (lambda x: x.account.code)),
            ((lambda x: label(x, 'description')), (lambda x: x.description)),
            ((lambda x: label(x, 'debit')), (lambda x: x.debit)),
            ((lambda x: label(x, 'credit')), (lambda x: x.credit)),
            ((lambda x: label(x, 'aggregated_move_id')), (lambda x:
                    x.aggregated_move_id)),
            ]

    @classmethod
    def get_filename(cls, output_folder, snapshot):
        return os.path.join(output_folder, '%s.csv' %
            snapshot.name)

    @classmethod
    def export_snapshot(cls, snap_id, output_folder):
        to_export = cls.fields_to_export()
        lines = Pool().get('account.move.line.aggregated').search(
            [('snapshot', '=', snap_id)])
        if lines:
            header = [cls.sanitize_value(x[0](lines[0])) for x in to_export]
            filename = cls.get_filename(output_folder, lines[0].snapshot)

            with open(filename, 'w+') as _f:
                writer = csv.writer(_f, delimiter=';')
                writer.writerow(header)
                for line in lines:
                    writer.writerow([cls.sanitize_value(
                                x[1](line)) for x in to_export])

    @classmethod
    def execute(cls, objects, ids, output_folder=None):
        pool = Pool()
        Snapshot = pool.get('account.move.snapshot')
        snap_id = Snapshot.take_snapshot()
        if output_folder:
            cls.export_snapshot(snap_id, output_folder)
        cls.logger.info('snapshot %s taken' % snap_id)

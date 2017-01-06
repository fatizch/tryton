# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging

from trytond.pool import Pool
from trytond.modules.coog_core import batch


__all__ = [
    'SnapshotTakeBatch',
    ]


class SnapshotTakeBatch(batch.BatchRootNoSelect):
    'Snapshot Moves Take batch'

    __name__ = 'account.move.snapshot.take'

    logger = logging.getLogger(__name__)

    @classmethod
    def execute(cls, objects, ids):
        pool = Pool()
        Snapshot = pool.get('account.move.snapshot')
        snap_id = Snapshot.take_snapshot()
        cls.logger.info('snapshot %s taken' % snap_id)

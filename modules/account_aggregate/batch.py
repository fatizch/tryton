
from celery.utils.log import get_task_logger

from trytond.pool import Pool
from trytond.modules.cog_utils import batch


__all__ = [
    'SnapshotTakeBatch',
    ]

logger = get_task_logger(__name__)


class SnapshotTakeBatch(batch.BatchRootNoSelect):
    'Snapshot Moves Take batch'

    __name__ = 'account.move.snapshot.take'

    @classmethod
    def execute(cls, objects, ids, treatment_date):
        pool = Pool()
        Snapshot = pool.get('account.move.snapshot')
        snap_id = Snapshot.take_snapshot()
        logger.info('take_snapshot end : snapshot id = %s' % snap_id)

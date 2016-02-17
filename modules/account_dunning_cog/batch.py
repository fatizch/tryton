import logging

from trytond.pool import Pool
from trytond.transaction import Transaction

from trytond.modules.cog_utils import batch

__all__ = [
    'DunningCreationBatch',
    'DunningTreatmentBatch',
    ]


class DunningCreationBatch(batch.BatchRoot):
    'Dunning Creation Batch'
    __name__ = 'account.dunning.create'

    logger = logging.getLogger(__name__)

    @classmethod
    def get_batch_main_model_name(cls):
        return 'account.dunning'

    @classmethod
    def get_batch_search_model(cls):
        return 'account.dunning'

    @classmethod
    def execute(cls, objects, ids, treatment_date, extra_args):
        Dunning = Pool().get('account.dunning')
        Dunning.generate_dunnings(treatment_date)
        cls.logger.info('Dunnings Generated Until %s' % treatment_date)


class DunningTreatmentBatch(batch.BatchRoot):
    'Process Dunning Batch'
    __name__ = 'account.dunning.treat'

    logger = logging.getLogger(__name__)

    @classmethod
    def get_batch_main_model_name(cls):
        return 'account.dunning'

    @classmethod
    def get_batch_search_model(cls):
        return 'account.dunning'

    @classmethod
    def select_ids(cls, treatment_date, extra_args):
        cursor = Transaction().cursor
        pool = Pool()
        dunning = pool.get('account.dunning').__table__()
        cursor.execute(*dunning.select(dunning.id,
            where=(dunning.state == 'draft'),
            order_by=dunning.level))
        return cursor.fetchall()

    @classmethod
    def execute(cls, objects, ids, treatment_date, extra_args):
        Dunning = Pool().get('account.dunning')
        Dunning.process(objects)
        cls.logger.info('Dunnings Process')

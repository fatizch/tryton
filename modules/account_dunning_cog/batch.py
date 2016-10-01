# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging

from trytond.pool import Pool

from trytond.modules.coog_core import batch

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

    @classmethod
    def get_batch_args_name(cls):
        return []


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
    def get_batch_domain(cls, treatment_date, extra_args):
        return [('state', '=', 'draft')]

    @classmethod
    def get_batch_ordering(cls):
        return [('level', 'DESC')]

    @classmethod
    def execute(cls, objects, ids, treatment_date, extra_args):
        Dunning = Pool().get('account.dunning')
        Dunning.process(objects)
        cls.logger.info('Dunnings Process')

    @classmethod
    def get_batch_args_name(cls):
        return []

# -*- coding:utf-8 -*-
import logging

from trytond.pool import Pool
from trytond.modules.cog_utils import batch


class ContractEndDateTerminationBatch(batch.BatchRoot):
    'Contract end date termination batch'

    __name__ = 'contract.termination.process'

    logger = logging.getLogger(__name__)

    @classmethod
    def get_batch_main_model_name(cls):
        return 'contract'

    @classmethod
    def get_batch_search_model(cls):
        return 'contract'

    @classmethod
    def get_batch_domain(cls, treatment_date, extra_args):
        return [['OR',
                ('status', '=', 'active'),
                ('status', '=', 'hold')],
            ('end_date', '!=', None),
            ('end_date', '<=', treatment_date)]

    @classmethod
    def execute(cls, objects, ids, treatment_date, extra_args):
        Contract = Pool().get('contract')
        Contract.do_terminate(objects)
        cls.logger.info('Terminated %d contracts.' % len(objects))

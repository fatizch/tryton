# -*- coding:utf-8 -*-
from trytond.pool import Pool
from trytond.modules.cog_utils import batchs


class ContractEndDateTerminationBatch(batchs.BatchRoot):
    'Contract end date termination batch'

    __name__ = 'contract.termination.treatment'

    @classmethod
    def get_batch_main_model_name(cls):
        return 'contract'

    @classmethod
    def get_batch_search_model(cls):
        return 'contract'

    @classmethod
    def get_batch_name(cls):
        return 'Contract end date termination batch'

    @classmethod
    def get_batch_stepping_mode(cls):
        return 'divide'

    @classmethod
    def get_batch_domain(cls, treatment_date):
        return [['OR',
                ('state', '=', 'active'),
                ('state', '=', 'hold')],
            ('end_date', '!=', None),
            ('end_date', '<=', treatment_date)]

    @classmethod
    def execute(cls, objects, ids, logger, treatment_date):
        logger.info('Starting contract end-date termination batch.')
        Contract = Pool().get('contract')
        Contract.terminate(objects)
        logger.info('Contract end-date termination batch ended.')

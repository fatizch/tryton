# -*- coding:utf-8 -*-
import logging

from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.modules.cog_utils import batch

from sql import Cast
from sql.functions import CurrentDate

__all__ = [
    'ContractEndDateTerminationBatch',
    'ContractDeclineInactiveQuotes',
    ]


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


class ContractDeclineInactiveQuotes(batch.BatchRoot):
    'Decline Inactive Quotes Contracts'
    __name__ = 'contract.decline.inactive_quotes'

    logger = logging.getLogger(__name__)

    @classmethod
    def get_batch_main_model_name(cls):
        return 'contract'

    @classmethod
    def select_ids(cls, treatment_date, extra_args):
        pool = Pool()
        cursor = Transaction().cursor
        configuration = pool.get('offered.configuration')(1)
        assert cls.check_batch_configuration(), \
            'Required product configuration is not specified.'
        contract = pool.get('contract').__table__()
        inactivity_delay = configuration.inactivity_delay
        sql_delay = (CurrentDate() - Cast(contract.write_date, 'DATE'))
        where_clause = (
            (contract.status == 'quote') &
            (sql_delay > inactivity_delay))
        cursor.execute(*contract.select(contract.id, where=where_clause))
        return cursor.fetchall()

    @classmethod
    def execute(cls, objects, ids, treatment_date, extra_args):
        pool = Pool()
        configuration = pool.get('offered.configuration')(1)
        Contract = pool.get('contract')
        reason = configuration.automatic_decline_reason
        assert cls.check_batch_configuration(), \
            'Contract configuration is not valid'
        Contract.decline_contract(objects, reason)

    @classmethod
    def check_batch_configuration(cls):
        configuration = Pool().get('offered.configuration')(1)
        return configuration.inactivity_delay and \
            configuration.automatic_decline_reason

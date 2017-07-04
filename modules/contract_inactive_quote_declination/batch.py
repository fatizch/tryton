# -*- coding:utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging
from dateutil.relativedelta import relativedelta

from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.modules.coog_core import batch


__all__ = [
    'ContractDeclineInactiveQuotes',
    ]


class ContractDeclineInactiveQuotes(batch.BatchRoot):
    'Decline Inactive Quotes Contracts'
    __name__ = 'contract.decline.inactive_quotes'

    logger = logging.getLogger(__name__)

    @classmethod
    def get_batch_main_model_name(cls):
        return 'contract'

    @classmethod
    def select_ids(cls, treatment_date):
        pool = Pool()
        cursor = Transaction().connection.cursor()
        configuration = pool.get('offered.configuration')(1)
        assert cls.check_batch_configuration(), \
            'Required product configuration is not specified.'
        contract = pool.get('contract').__table__()
        inactivity_delay = configuration.inactivity_delay
        if configuration.delay_unit == 'month':
            maturity_date = treatment_date - relativedelta(
                months=+inactivity_delay)
        else:
            maturity_date = treatment_date - relativedelta(
                days=+inactivity_delay)
        where_clause = (
            (contract.status == 'quote') &
            (contract.write_date < maturity_date))
        cursor.execute(*contract.select(contract.id, where=where_clause))
        return cursor.fetchall()

    @classmethod
    def execute(cls, objects, ids, treatment_date):
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
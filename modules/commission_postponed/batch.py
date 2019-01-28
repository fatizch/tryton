# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging
from sql import Literal, Null

from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from trytond.modules.coog_core import batch


__all__ = [
    'CommissionPostponedCalculate',
    'CreateCommissionInvoiceBatch',
    ]


class CommissionPostponedCalculate(batch.BatchRoot):
    'Calculate posponed commission'

    __name__ = 'commission.postponed.calculate'

    logger = logging.getLogger(__name__)

    @classmethod
    def get_batch_main_model_name(cls):
        return 'commission'

    @classmethod
    def select_ids(cls, treatment_date):
        cursor = Transaction().connection.cursor()
        commission = Pool().get('commission').__table__()

        query = commission.select(commission.id,
               where=((commission.postponed == Literal(True)) &
               (commission.date <= treatment_date)))
        cursor.execute(*query)
        return cursor.fetchall()

    @classmethod
    def execute(cls, objects, ids, treatment_date):
        Commission = Pool().get('commission')
        Commission.calculate_postponed_commission_amount(objects)


class CreateCommissionInvoiceBatch(metaclass=PoolMeta):

    __name__ = 'commission.invoice.create'

    @classmethod
    def get_where_clause(cls, tables, treatment_date, agent_type):
        commission = tables['commission']
        return super(CreateCommissionInvoiceBatch, cls).get_where_clause(
            tables, treatment_date, agent_type) & (
                (commission.postponed == Literal(False)) | (
                    commission.postponed == Null))

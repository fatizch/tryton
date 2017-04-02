# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging

from trytond.pool import Pool
from trytond.transaction import Transaction

from trytond.modules.coog_core import batch

__all__ = [
    'UnderwritingActivationBatch',
    ]


class UnderwritingActivationBatch(batch.BatchRoot):
    'Underwriting Activation Batch'

    __name__ = 'underwriting.activate'

    logger = logging.getLogger(__name__)

    @classmethod
    def get_batch_main_model_name(cls):
        return 'underwriting'

    @classmethod
    def get_batch_search_model(cls):
        return 'underwriting'

    @classmethod
    def select_ids(cls, treatment_date):
        pool = Pool()
        Type = pool.get('underwriting.type')
        underwriting = pool.get('underwriting').__table__()
        result = pool.get('underwriting.result').__table__()
        cursor = Transaction().connection.cursor()

        automatic_types = Type.search([('manual_activation', '=', False)])
        if not automatic_types:
            return []

        cursor.execute(*underwriting.join(result, condition=(
                    result.underwriting == underwriting.id)
                ).select(underwriting.id, where=(underwriting.state == 'draft')
                & (result.effective_decision_date <= treatment_date)
                & underwriting.type_.in_([x.id for x in automatic_types]),
                group_by=[underwriting.id]))
        return cursor.fetchall()

    @classmethod
    def execute(cls, objects, ids, treatment_date):
        Pool().get('underwriting').process(objects)
        cls.logger.info('Done processing %s underwritings' % str(len(ids)))
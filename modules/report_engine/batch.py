# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging
from itertools import groupby

from trytond.pool import Pool
from trytond.transaction import Transaction

from trytond.modules.coog_core import batch


__all__ = [
    'ReportProductionRequestTreatmentBatch',
    ]


class ReportProductionRequestTreatmentBatch(batch.BatchRoot):
    'Report Production Request Treatment Batch'

    __name__ = 'report_production.request.batch_treat'

    logger = logging.getLogger(__name__)

    @classmethod
    def get_batch_main_model_name(cls):
        return 'report.template'

    @classmethod
    def select_ids(cls):
        pool = Pool()
        cursor = Transaction().connection.cursor()
        main_table = pool.get('report_production.request').__table__()
        query = main_table.select(main_table.report_template,
            where=(main_table.treated == False),
            group_by=[main_table.report_template])
        cursor.execute(*query)
        return cursor.fetchall()

    @classmethod
    def execute(cls, objects, ids):
        pool = Pool()
        ProductionRequest = pool.get('report_production.request')
        ReportProductionRequest = pool.get('report_production.request')
        objects = ProductionRequest.search([('report_template', 'in', ids),
                ('treated', '=', False)])
        reports, attachments = ReportProductionRequest.treat_requests(objects)
        cls.logger.info('Produced %s reports, and created %s attachments' %
            (len(reports), len(attachments)))

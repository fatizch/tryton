# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging
from sql import Literal, Null
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
    def __setup__(cls):
        super(ReportProductionRequestTreatmentBatch, cls).__setup__()
        cls._default_config_items.update({
                'job_size': 1,
                })

    @classmethod
    def get_batch_main_model_name(cls):
        return 'report_production.request'

    @classmethod
    def select_ids(cls):
        cursor = Transaction().connection.cursor()
        ProductionRequest = Pool().get('report_production.request')
        main_table = ProductionRequest.__table__()
        query = main_table.select(main_table.report_template, main_table.id,
            where=(main_table.treated == Literal(False) &
                (main_table.report_template != Literal(Null))),
            order_by=[main_table.report_template])
        cursor.execute(*query)
        records = [(tmpl, req) for tmpl, req in cursor.fetchall()]
        selected = []
        for template, requests in groupby(records, lambda x:
                x[0]):
            selected.append([(x[1],) for x in requests])
        return selected

    @classmethod
    def execute(cls, objects, ids):
        ReportProductionRequest = Pool().get('report_production.request')
        reports, attachments = ReportProductionRequest.treat_requests(objects)
        cls.logger.info('Produced %s reports, and created %s attachments' %
            (len(reports), len(attachments)))

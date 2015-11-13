from trytond.pool import Pool

from trytond.modules.cog_utils import batch


__all__ = [
    'ReportProductionRequestTreatmentBatch',
    ]


class ReportProductionRequestTreatmentBatch(batch.BatchRoot):
    'Report Production Request Treatment Batch'

    __name__ = 'report_production.request.batch_treat'

    logger = batch.get_logger(__name__)

    @classmethod
    def get_batch_main_model_name(cls):
        return 'report_production.request'

    @classmethod
    def get_batch_search_model(cls):
        return 'report_production.request'

    @classmethod
    def get_batch_domain(cls, treatment_date, extra_args):
        return [('treated', '=', False)]

    @classmethod
    def execute(cls, objects, ids, treatment_date, extra_args):
        pool = Pool()
        ReportProductionRequest = pool.get('report_production.request')
        reports, attachments = ReportProductionRequest.treat_requests(objects)
        cls.logger.info('Produced %s reports, and created %s attachments' %
            (len(reports), len(attachments)))

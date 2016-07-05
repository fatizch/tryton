# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging

from trytond.pool import Pool
from trytond.transaction import Transaction

from trytond.modules.cog_utils import batch, coop_date

__all__ = [
    'DocumentRequestBatch',
    ]


class DocumentRequestBatch(batch.BatchRoot):
    'Document Request Batch Definition'

    __name__ = 'document.request.process'

    logger = logging.getLogger(__name__)

    @classmethod
    def get_batch_main_model_name(cls):
        return 'document.request'

    @classmethod
    def get_batch_search_model(cls):
        return 'document.request.line'

    @classmethod
    def get_batch_field(cls):
        return 'request'

    @classmethod
    def get_batch_ordering(cls):
        return [('request', 'ASC')]

    @classmethod
    def get_batch_domain(cls, treatment_date, extra_args):
        return [
            ('reception_date', '=', None),
            [
                'OR',
                ('send_date', '=', None),
                ('send_date', '<=', coop_date.add_month(treatment_date, -3))]]

    @classmethod
    def execute(cls, objects, ids, treatment_date, extra_args):
        ReportCreate = Pool().get(
            'report.create', type='wizard')
        for cur_object in objects:
            with Transaction().set_context(
                    active_model=cur_object.__name__, active_id=cur_object.id):
                wizard_id, _, _ = ReportCreate.create()
                wizard = ReportCreate(wizard_id)
                data = wizard.execute(wizard_id, {}, 'select_model')
                data = wizard.execute(wizard_id, {
                    'select_model': data['view']['defaults']}, 'generate')
                report_def, data = data['actions'][0]
                Report = Pool().get(report_def['report_name'], type='report')
                ext, _buffer, _, name = Report.execute([data['id']], data)
                cls.write_batch_output(_buffer, '%s.%s' % (name, ext))
                wizard.execute(wizard_id, {}, 'post_generation')
                cls.logger.info('Processed report request for %s' %
                    cur_object.get_rec_name(None))

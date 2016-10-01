# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging

from trytond.pool import Pool
from trytond.transaction import Transaction

from trytond.modules.coog_core import batch, coog_date

__all__ = [
    'DocumentRequestBatch',
    'BatchRemindDocuments',
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
                ('send_date', '<=', coog_date.add_month(treatment_date, -3))]]

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


class BatchRemindDocuments(batch.BatchRoot):
    'Batch Remind Documents'

    __name__ = 'batch.remind.documents'

    logger = logging.getLogger(__name__)

    @classmethod
    def convert_to_instances(cls, ids):
        return []

    @classmethod
    def select_ids(cls, treatment_date, extra_args=None):
        on_model = extra_args.get('on_model', False)
        assert on_model, 'The parameter on_model is required'
        Model = Pool().get(on_model)
        return Model.get_reminder_candidates()

    @classmethod
    def execute(cls, objects, ids, treatment_date, extra_args):
        on_model = extra_args.get('on_model', False)
        assert on_model, 'The parameter on_model is required'
        Model = Pool().get(on_model)
        assert hasattr(Model, 'get_reminder_candidates'), \
            '%s does not implement get_reminder_candidates' % Model.__name__
        objects = Model.browse(ids)
        with Transaction().set_context(force_remind=False):
            Model.generate_reminds_documents(objects,
                treatment_date=treatment_date)

    @classmethod
    def get_batch_args_name(cls):
        return ['on_model']

from trytond.pool import PoolMeta, Pool
from trytond.wizard import Wizard, StateAction, StateTransition
from trytond.transaction import Transaction

from trytond.modules.coog_core import utils


__all__ = [
    'ReportTemplate',
    'DocumentRequestReport',
    ]


class ReportTemplate:
    __metaclass__ = PoolMeta
    __name__ = 'report.template'

    def get_possible_kinds(self):
        result = super(ReportTemplate, self).get_possible_kinds()
        if not self.on_model:
            return result
        if self.on_model.model == 'claim':
            result.append(('claim_doc_requests', 'Claim Document Requests'))
        return result


class DocumentRequestReport(Wizard):
    'Document Request Report Wizard'
    __name__ = 'document.request.report'

    start_state = 'generate_requests'
    generate_requests = StateTransition()
    launch_report = StateAction('report_engine.letter_generation_wizard')

    @classmethod
    def __setup__(cls):
        super(DocumentRequestReport, cls).__setup__()
        cls._error_messages.update({
                'no_documents_required': 'No documents are required.',
                'document_request_sent': 'Document requests sent:\n %s'
                })

    def transition_generate_requests(self):
        pool = Pool()
        transaction_ctx = Transaction().context

        Event = pool.get('event')
        Model = pool.get(transaction_ctx.get('active_model'))
        DocumentRequest = pool.get('document.request.line')

        instance = Model(transaction_ctx.get('active_id'))
        documents = [doc for doc in instance.document_request_lines
            if not doc.received]
        if not documents:
            self.raise_user_error('no_documents_required')
        documents_str = '\n'.join(
            ['- %s' % doc.document_desc.code for doc in documents])
        description = self.raise_user_error(
            'document_request_sent', documents_str, raise_exception=False)
        DocumentRequest.write(documents, {'send_date': utils.today()})
        Event.notify_events([instance], 'sent_document_requests',
            description=description)
        return 'launch_report'

    def do_launch_report(self, action):
        transaction_ctx = Transaction().context
        return (action, {
                'extra_context': {'report_kind': 'claim_doc_requests'},
                'id': transaction_ctx.get('active_id'),
                'ids': transaction_ctx.get('active_ids'),
                'model': transaction_ctx.get('active_model')
                })

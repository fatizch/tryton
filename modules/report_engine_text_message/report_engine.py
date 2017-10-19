# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.modules.coog_core import fields, model
from trytond.pyson import Or, Eval


__all__ = [
    'ReportGenerate',
    'ReportTemplate',
    'ReportCreate',
    ]


class ReportGenerate:
    __metaclass__ = PoolMeta
    __name__ = 'report.generate'

    @classmethod
    def process_send_text_message(cls, ids, data, **kwargs):
        """
        Generic sending method which generates and sends the text message using
        the process method defined on the report template.
        """
        records = cls._get_records(ids, data['model'], data)
        selected_letter = Pool().get('report.template')(
            data['doc_template'][0])
        cls.send_text_message(selected_letter, records)
        return None, None, False, None

    @classmethod
    def send_text_message(cls, selected_letter, records):
        """
        Generic method which calls the right method sending function according
        to service defined on the selected letter
        """
        headers = cls.generate_message_header(selected_letter, records)
        send_method = getattr(cls, '%s_send_message' %
            selected_letter.process_method or 'default', None)
        if not send_method:
            raise NotImplementedError('Unknown kind %s' %
                selected_letter.process_method or 'default')
        for record in records:
            data = cls.generate_message_data(selected_letter, record)
            cls.check_send_errors(send_method(headers, data, selected_letter),
                selected_letter.process_method)

    @classmethod
    def check_send_errors(cls, result, process_method):
        """
        Check if an error occurs while sending the text message.
        Result is the return value of the sending method.
        Usually, the input 'result' parameter should be the result of the text
        message API call.
        """
        pass

    @classmethod
    def default_send_message(cls, headers, data, selected_letter):
        """
        Called if no service has been specified on the report template
        or if the [service]_send_message is not found on the ReportGenerate
        model.
        The method should send the header and the data generate
        """
        raise NotImplementedError

    @classmethod
    def generate_message_header(cls, selected_letter, records):
        """
        Generates the header to be given to the text message service API.
        This should be overwritten for each service implementation
        Returns a dictionnary which define the headers
        """
        return {}

    @classmethod
    def generate_message_data(cls, selected_letter, record):
        """
        Generates the data to be given to the text message service API.
        This should be overwritten for each service implementation.
        Returns a dictionnary which defines the data
        """
        data = {
            'number': selected_letter.genshi_evaluated_phone_number,
            'message': selected_letter.genshi_evaluated_message.encode(
                'utf-8'),
            }
        if selected_letter.message_sender:
            data['sender'] = selected_letter.genshi_evaluated_message_sender
        return data


@model.genshi_evaluated_fields('message_sender', 'phone_number', 'message')
class ReportTemplate:
    __metaclass__ = PoolMeta
    __name__ = 'report.template'

    message_sender = fields.Char('Message Sender',
        states={'invisible': Eval('input_kind') != 'text_message'},
        depends=['input_kind'],
        help='The message sender name, (3-11 alphanumeric characters or '
        'dynamic expression)')
    phone_number = fields.Char('Phone Number', states={
            'invisible': Eval('input_kind') != 'text_message',
            'required': Eval('input_kind') == 'text_message',
            }, depends=['input_kind'],
        help='Recipient Phone Number (0XXXXXXXXX or +33XXXXXXXXXX or '
        'dynamic expression')
    message = fields.Text('Message', states={
            'invisible': Eval('input_kind') != 'text_message',
            'required': Eval('input_kind') == 'text_message',
            }, depends=['input_kind'],
        help='Dynamic expressions (genshi) are supported')

    @classmethod
    def __setup__(cls):
        super(ReportTemplate, cls).__setup__()
        for fname in ['modifiable_before_printing', 'document_desc',
                'versions', 'export_dir', 'format_for_internal_edm',
                'output_filename', 'export_dir', 'split_reports']:
            field = getattr(cls, fname)
            field.states['invisible'] = Or(Eval('input_kind') ==
                'text_message', field.states.get('invisible', False))
            field.depends.append('input_kind')
        cls._error_messages.update({
                'input_text_message': 'Text Message',
                })

    @classmethod
    def get_possible_input_kinds(cls):
        return super(ReportTemplate, cls).get_possible_input_kinds() + \
            [('text_message', cls.raise_user_error('input_text_message',
                        raise_exception=False))]

    @fields.depends('input_kind')
    def get_possible_process_methods(self):
        if self.input_kind == 'text_message':
            return []
        return super(ReportTemplate, self).get_possible_process_methods()

    @fields.depends('input_kind')
    def on_change_input_kind(self):
        if self.input_kind == 'text_message':
            self.split_reports = True
            self.format_for_internal_edm = ''
        else:
            self.message_sender = ''
            self.phone_number = ''
            self.message = ''
        super(ReportTemplate, self).on_change_input_kind()


class ReportCreate:
    __metaclass__ = PoolMeta
    __name__ = 'report.create'

    def report_execute(self, ids, doc_template, report_context):
        if doc_template.input_kind != 'text_message':
            return super(ReportCreate, self).report_execute(ids, doc_template,
                report_context)
        ReportModel = Pool().get('report.generate', type='report')
        ReportModel.execute(ids, report_context)
        return {}

    def transition_generate(self):
        next_state = super(ReportCreate, self).transition_generate()
        if self.select_template.template.input_kind == 'text_message':
            return 'end'
        return next_state

    def finalize_report(self, report, instances):
        if self.select_template.template.input_kind == 'text_message':
            return
        return super(ReportCreate, self).finalize_report(report, instances)

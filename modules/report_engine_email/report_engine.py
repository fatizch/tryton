# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import os
import base64
import logging
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from itertools import izip

from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from trytond.server_context import ServerContext
from trytond.report import Report
from trytond.pyson import Eval, Or
from trytond.sendmail import sendmail, sendmail_transactional
from trytond.wizard import Button, StateAction

from trytond.modules.coog_core import fields, model


__metaclass__ = PoolMeta

__all__ = [
    'ReportGenerate',
    'ReportGenerateEmail',
    'ReportTemplate',
    'ReportCreate',
    'ReportCreateSelectTemplate',
    'TemplateTemplateRelation',
    'ImageAttachment',
    'ReportTemplateImageAttachmentRelation',
    ]

EMAIL_REQUIRED_STATES = {
    'invisible': Eval('input_kind') != 'email',
    'required': Eval('input_kind') == 'email',
    }


class ImageAttachment(model.CoogSQL, model.CoogView):
    'Image Attachment'

    __name__ = 'report.template.image_attachment'

    name = fields.Char('Name', required=True)
    image = fields.Binary('Image', filename='name', required=True)


class ReportTemplateImageAttachmentRelation(model.CoogSQL, model.CoogView):
    'Report Template Image attachment Relation'

    __name__ = 'report.template-report.template.image_attachment'

    template = fields.Many2One('report.template', 'Template',
        ondelete='CASCADE', required=True, select=True)
    image = fields.Many2One('report.template.image_attachment', 'Image',
        ondelete='CASCADE', required=True, select=True)


class TemplateTemplateRelation(model.CoogSQL, model.CoogView):
    'Template Template Relation'

    __name__ = 'report.template.report.template.relation'

    parent_template = fields.Many2One('report.template', 'Template',
        ondelete='CASCADE', required=True, select=True)
    child_template = fields.Many2One('report.template', 'Template',
        ondelete='RESTRICT', required=True, select=True)


class ReportGenerate:
    __name__ = 'report.generate'

    @classmethod
    def get_context(cls, records, data):
        context_ = super(ReportGenerate, cls).get_context(records, data)
        context_['record'] = records[0]
        template = Pool().get('report.template')(data['doc_template'][0])
        context_['images'] = {}
        for image in template.images:
            context_['images'][os.path.splitext(image.name)[0]] = \
                base64.b64encode(image.image)
        return context_

    @classmethod
    def generate_email(self, selected_letter, cur_objects, report_context):
        attachments = []
        if selected_letter.attachments or selected_letter.images:
            fake_event_action = Pool().get('event.type.action')()
            for tmpl in selected_letter.attachments:
                fake_event_action.report_templates = [tmpl]
                valid_objects = fake_event_action.filter_objects_for_report(
                    cur_objects, tmpl)
                generated_reports = tmpl._generate_reports(valid_objects, {})
                if tmpl.format_for_internal_edm:
                    tmpl.save_reports_in_edm(generated_reports)
                attachments += generated_reports
            if attachments or selected_letter.images:
                if selected_letter.html_body:
                    msg = MIMEMultipart('related')
                    msg.attach(MIMEText(
                            selected_letter.genshi_evaluated_email_body.encode(
                                'utf-8'),
                            'html'))
                else:
                    msg = MIMEMultipart(
                        selected_letter.genshi_evaluated_email_body.encode(
                            'utf-8'))
                for i, attachment in enumerate(attachments):
                    part = MIMEApplication(attachment['data'])
                    part.add_header('Content-Disposition', 'attachment',
                        filename=('%s_%s' % (i, attachment['report_name'])
                            ).encode('utf-8'))
                    msg.attach(part)
                for image in selected_letter.images:
                    img = MIMEImage(image.image)
                    img.add_header('Content-Id', '<%s>' % image.name)
                    msg.attach(img)
        else:
            if selected_letter.html_body:
                msg = MIMEMultipart('related')
                msg.attach(MIMEText(
                        selected_letter.genshi_evaluated_email_body.encode(
                            'utf-8'),
                        'html'))
            else:
                msg = MIMEText(
                    selected_letter.genshi_evaluated_email_body.encode(
                        'utf-8'))
        msg['From'] = selected_letter.genshi_evaluated_email_sender
        msg['To'] = selected_letter.genshi_evaluated_email_dest
        msg['Cc'] = selected_letter.genshi_evaluated_email_cc
        # We must not set BCC header. Bcc is implicit because the mail is sent
        # to recipients + cc + others which will be implicitly hidden.
        msg['Subject'] = selected_letter.genshi_evaluated_email_subject.encode(
            'utf-8')
        return {
            'message': msg,
            'attachments': attachments,
            }

    @classmethod
    def process_email(cls, ids, data, **kwargs):
        records = cls._get_records(ids, data['model'], data)
        report_context = cls.get_context(records, data)
        send = ServerContext().get('auto_send', True)
        selected_letter = Pool().get('report.template')(
            data['doc_template'][0])
        data_email = cls.generate_email(selected_letter, records,
            report_context)
        msg = data_email['message']
        attachments = data_email['attachments']
        cc = [x.strip() for x in
            selected_letter.genshi_evaluated_email_cc.split(',')]
        bcc = [x.strip() for x in
            selected_letter.genshi_evaluated_email_bcc.split(',')]
        recipients = [x.strip() for x in
            selected_letter.genshi_evaluated_email_dest.split(',')]
        if not send:
            return ([x['report_type'] for x in attachments],
                [x['data'] for x in attachments],
                    False, [x['report_name'] for x in attachments])
        if not selected_letter.email_blocking:
            try:
                sendmail(
                    selected_letter.genshi_evaluated_email_sender,
                    recipients + cc + bcc, msg)
                logging.getLogger('report.generate').info(
                    'Mail sent to %s' % recipients)
            except Exception as e:
                logging.getLogger('report.generate').error(
                    'Could not send email for template %s. Error : %s' %
                    (str(selected_letter), str(e)))
                selected_letter.raise_user_error('email_not_sent')
        else:
            sendmail_transactional(
                selected_letter.genshi_evaluated_email_sender,
                recipients + cc + bcc, msg, Transaction())
        return ([x['report_type'] for x in attachments],
            [x['data'] for x in attachments],
                False, [x['report_name'] for x in attachments])


@model.genshi_evaluated_fields('email_sender', 'email_dest', 'email_cc',
    'email_bcc', 'email_subject', 'email_body')
class ReportTemplate:
    __name__ = 'report.template'

    email_sender = fields.Char('Email Sender', states=EMAIL_REQUIRED_STATES,
        depends=['input_kind'])
    email_dest = fields.Char('Email Recipients', states=EMAIL_REQUIRED_STATES,
        depends=['input_kind'])
    email_cc = fields.Char('Email CC', states={
            'invisible': Eval('input_kind') != 'email'},
        depends=['input_kind'])
    email_bcc = fields.Char('Email BCC', states={
            'invisible': Eval('input_kind') != 'email'},
        depends=['input_kind'])
    email_subject = fields.Char('eMail Subject', states={
            'invisible': Eval('input_kind') != 'email'},
        depends=['input_kind'])
    html_body = fields.Boolean('HTML Body', states={
            'invisible': Eval('input_kind') != 'email'},
        depends=['input_kind'])
    email_body = fields.Text('eMail Body', states={
            'invisible': Eval('input_kind') != 'email'},
        depends=['input_kind'])
    email_blocking = fields.Boolean('Email is blocking', states={
            'invisible': Eval('input_kind') != 'email',
            },
        depends=['input_kind'])
    allow_manual_sending = fields.Boolean('Allow Manual Sending', states={
            'invisible': Eval('input_kind') != 'email',
            },
        help='Be careful: Do not exceed the operating system max command '
        'line length with your attachments',
        depends=['input_kind'])
    attachments = fields.Many2Many(
        'report.template.report.template.relation', 'parent_template',
        'child_template', 'Attachments', states={
            'invisible': Eval('input_kind') != 'email'},
        domain=[('input_kind', '!=', 'email'), ('on_model', '=',
                Eval('on_model'))],
        depends=['on_model'])
    images = fields.Many2Many(
        'report.template-report.template.image_attachment',
        'template', 'image', 'Images', states={
            'invisible': Eval('input_kind') != 'email'},
        depends=['on_model'])

    @classmethod
    def __setup__(cls):
        super(ReportTemplate, cls).__setup__()
        for fname in ['modifiable_before_printing', 'document_desc',
                'versions', 'export_dir', 'format_for_internal_edm',
                'output_filename']:
            field = getattr(cls, fname)
            field.states['invisible'] = Or(Eval('input_kind') == 'email',
                field.states.get('invisible', False))
            field.depends.append('input_kind')
        cls._error_messages.update({'email_not_sent':
                'The email could not be sent',
                'manual_send': 'The template does not allow email editing',
                'input_email': 'Email',
                'split_email': 'Split reports on email templates is'
                ' recommended, you must be sure of your genshi fields',
                })

    @classmethod
    def validate(cls, records):
        super(ReportTemplate, cls).validate(records)
        for record in records:
            if record.input_kind == 'email' and not record.split_reports:
                cls.raise_user_warning(str(record), 'split_email')

    @classmethod
    def view_attributes(cls):
        return super(ReportTemplate, cls).view_attributes() + [(
                '/form/notebook/page[@id="versions"]', 'states',
                {'invisible': getattr(cls, 'versions').states.get(
                        'invisible')}),
                ('/form/notebook/page[@id="attachments"]', 'states',
                {'invisible': getattr(cls, 'attachments').states.get(
                        'invisible')})
            ]

    @classmethod
    def get_possible_input_kinds(cls):
        return super(ReportTemplate, cls).get_possible_input_kinds() + \
            [('email', cls.raise_user_error('input_email',
                        raise_exception=False))]

    @fields.depends('input_kind', 'email_subject',
        'email_body', 'email_blocking,' 'split_reports', 'email_dest',
        'email_cc', 'email_bcc', 'email_sender', 'atachments')
    def on_change_input_kind(self):
        if self.input_kind == 'email':
            self.split_reports = True
            self.attachments = []
            self.output_filename = ''
            self.version = []
        else:
            self.email_dest = ''
            self.email_subject = ''
            self.email_body = ''
            self.email_blocking = False
            self.email_cc = ''
            self.email_bcc = ''
            self.email_sender = ''
        super(ReportTemplate, self).on_change_input_kind()

    @fields.depends('input_kind')
    def get_possible_process_methods(self):
        if self.input_kind == 'email':
            return [('email', self.raise_user_error('input_email',
                        raise_exception=False))]
        return super(ReportTemplate, self).get_possible_process_methods()

    def print_reports(self, reports, context_):
        if self.input_kind == 'email':
            return None
        return super(ReportTemplate, self).print_reports(reports, context_)


class ReportGenerateEmail(Report):
    __name__ = 'report.generate_email'

    @classmethod
    def execute(cls, ids, data, **kwargs):
        filenames = data['attachments']
        types = data['types']
        base_path = data['path']
        contents = []
        for fname in filenames:
            with open(os.path.join(base_path, fname), 'rb') as _f:
                contents.append(bytearray(_f.read()))
        return types, contents, False, [os.path.splitext(x)[0] for x in
            filenames]


class ReportCreateSelectTemplate:
    __name__ = 'report.create.select_template'

    recipient_email = fields.Many2One('party.contact_mechanism',
        'Recipient Email', states={'invisible': ~Eval('recipient')
            | ~Eval('template')},
        domain=[('party', '=', Eval('recipient')),
            ('type', '=', 'email')],
        depends=['recipient'])
    manual_send_email = fields.Boolean('Manual Send Email')

    @fields.depends('template')
    def on_change_with_manual_send_email(self):
        if self.template and self.template.process_method == 'email':
            return self.template.allow_manual_sending
        return False

    @fields.depends('recipient', 'recipient_address', 'recipient_email')
    def on_change_recipient(self):
        super(ReportCreateSelectTemplate, self).on_change_recipient()
        if not self.recipient:
            self.recipient_email = None


class ReportCreate:
    __name__ = 'report.create'

    open_email = StateAction('report_engine_email.generate_email')

    @classmethod
    def __setup__(cls):
        super(ReportCreate, cls).__setup__()
        cls.select_template.buttons.extend([
                Button('Manual eMail sending', 'open_email',
                    'tryton-print-email', states={
                        'invisible': ~Eval('manual_send_email')})])

    def report_execute(self, ids, doc_template, report_context):
        if doc_template.input_kind != 'email':
            return super(ReportCreate, self).report_execute(ids, doc_template,
                report_context)
        ReportModel = Pool().get('report.generate', type='report')
        ReportModel.execute(ids, report_context)
        return {}

    def transition_generate(self):
        next_state = super(ReportCreate, self).transition_generate()
        if self.select_template.template.input_kind == 'email':
            return 'end'
        return next_state

    def finalize_report(self, report, instances):
        if self.select_template.template.input_kind == 'email':
            return
        return super(ReportCreate, self).finalize_report(report, instances)

    def do_open_email(self, action):
        if (not self.select_template.template or
                self.select_template.template.input_kind != 'email' or
                not self.select_template.template.allow_manual_sending):
            self.select_template.template.raise_user_error('manual_send')
        ReportGenerate = Pool().get('report.generate', type='report')
        report_context = self.create_report_context()
        with ServerContext().set_context(auto_send=False):
            types, attachments, _, filenames = ReportGenerate.execute(
                report_context['ids'], report_context)
        action['email_print'] = True
        report_context = self.create_report_context()
        records = ReportGenerate._get_records(report_context['ids'],
            report_context['model'], report_context)
        report_context = ReportGenerate.get_context(records, report_context)
        with ServerContext().set_context(genshi_context=report_context):
            tmpl = self.select_template
            if tmpl.recipient_email:
                recipients = tmpl.recipient_email.email
            else:
                recipients = \
                    tmpl.template.genshi_evaluated_email_dest
            action['email'] = {
                'to': recipients,
                'cc': tmpl.template.genshi_evaluated_email_cc,
                'bcc': tmpl.template.genshi_evaluated_email_bcc,
                'from':
                tmpl.template.genshi_evaluated_email_sender,
                'subject':
                tmpl.template.genshi_evaluated_email_subject.encode('utf-8'),
                'body':
                tmpl.template.genshi_evaluated_email_body.encode('utf-8'),
                }

        _, base_path = ReportGenerate.create_shared_tmp_dir()
        for content, filename in izip(attachments, filenames):
            with open(os.path.join(base_path, filename), 'wb') as _f:
                _f.write(content)
        return action, {
            'attachments': filenames,
            'types': types,
            'path': base_path,
            }

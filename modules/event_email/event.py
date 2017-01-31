# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from genshi.template import TextTemplate

from trytond.pool import PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.sendmail import sendmail, sendmail_transactional

from trytond.modules.coog_core import fields

__all__ = [
    'EventTypeAction',
    ]


class EventTypeAction:
    __metaclass__ = PoolMeta
    __name__ = 'event.type.action'

    email_sender = fields.Char('Email Sender', states={
            'invisible': Eval('action') != 'send_email',
            'required': Eval('action') == 'send_email',
            },
        depends=['action'])
    email_dest = fields.Char('Email Recipients', states={
            'invisible': Eval('action') != 'send_email',
            'required': Eval('action') == 'send_email',
            },
        depends=['action'])
    email_subject = fields.Char('Email Subject', states={
            'invisible': Eval('action') != 'send_email',
            'required': Eval('action') == 'send_email',
            },
        depends=['action'])
    email_body = fields.Text('Email Body', states={
            'invisible': Eval('action') != 'send_email',
            'required': Eval('action') == 'send_email',
            },
        help='You can use the "${object.field_name}" syntax to access fields '
        'from the object which triggered the event',
        depends=['action'])
    email_blocking = fields.Boolean('Email is blocking', states={
            'invisible': Eval('action') != 'send_email',
            },
        depends=['action'])
    group_emails = fields.Boolean('Group Emails', states={
            'invisible': Eval('action') != 'send_email',
            }, help='If True, grouped events will only send one email. The '
        '"object" keyword in the body templating will hold a list rather than '
        'a single instance.',
        depends=['action'])
    attachment_template = fields.Many2One('report.template',
        'Attachement Template', states={
            'invisible': Eval('action') != 'send_email',
            }, depends=['action'], ondelete='RESTRICT')

    @classmethod
    def get_action_types(cls):
        return super(EventTypeAction, cls).get_action_types() + [
            ('send_email', 'Send Email')]

    @fields.depends('email_body', 'email_dest', 'email_sender',
        'email_subject')
    def on_change_action(self):
        super(EventTypeAction, self).on_change_action()
        self.email_desc = ''
        self.email_body = ''
        self.email_sender = ''
        self.email_subject = ''

    def execute(self, objects, event_code, description=None, **kwargs):
        if self.action != 'send_email':
            return super(EventTypeAction, self).execute(objects, event_code)
        for cur_object in [objects] if self.group_emails else objects:
            kwargs['object'] = cur_object
            msg = self.generate_email(kwargs)
            recipients = [x.strip() for x in self.email_dest.split(',')]
            if not self.email_blocking:
                try:
                    sendmail(self.email_sender, recipients, msg)
                except Exception as e:
                    logging.getLogger('events').error('Could not send email '
                        'for event %s. Error : %s' % (event_code, str(e)))
            else:
                sendmail_transactional(self.email_sender, recipients, msg,
                    Transaction())

    def generate_email(self, data):
        template = TextTemplate(self.email_body)
        cur_object = data['object']
        if self.attachment_template:
            attachments = self.attachment_template._generate_reports(
                [cur_object] if not isinstance(cur_object, list) else
                cur_object, {})
            if attachments:
                msg = MIMEMultipart(template.generate(**data).render())
                for i, attachment in enumerate(attachments):
                    part = MIMEApplication(
                        attachment['data'],
                        Name='%s_%s' % (i, attachment['report_name']),
                        )
                    msg.attach(part)
            else:
                msg = MIMEText(template.generate(**data).render())
        msg['From'] = self.email_sender
        msg['To'] = self.email_dest
        msg['Subject'] = self.email_subject
        return msg

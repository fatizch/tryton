# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.modules.coog_core import fields
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, Bool

from trytond.modules.coog_core import utils

__all__ = [
    'DocumentDescription',
    'DocumentRequestLine',
    ]


class DocumentDescription:
    __metaclass__ = PoolMeta
    __name__ = 'document.description'

    digital_signature_required = fields.Boolean('Digital Signature Required',
        states={'invisible': ~Eval('reception_requires_attachment')},
        depends=['reception_requires_attachment'])

    @fields.depends('digital_signature_required',
        'reception_requires_attachment')
    def on_change_reception_requires_attachment(self):
        if not self.reception_requires_attachment:
            self.digital_signature_required = False


class DocumentRequestLine:
    __metaclass__ = PoolMeta
    __name__ = 'document.request.line'

    digital_signature_required = fields.Function(
        fields.Boolean('Digital Signature Required'),
        'get_digital_signature_required')
    electronic_signature_icon = fields.Function(
        fields.Char('Electronic Signature Icon'),
        'on_change_with_electronic_signature_icon')

    @classmethod
    def __setup__(cls):
        super(DocumentRequestLine, cls).__setup__()
        cls.attachment_data.states = {'readonly':
            Bool(Eval('digital_signature_required'))}
        cls.attachment_data.depends += ['digital_signature_required']
        cls.received.help = 'If a digital signature is required ' \
            + 'the document cannot be marked as received unless signed.'

    def get_digital_signature_required(self, name):
        return self.document_desc.digital_signature_required

    @fields.depends('digital_signature_required', 'attachment')
    def on_change_with_electronic_signature_icon(self, name=None):
        if self.digital_signature_required:
            if not (self.attachment and
                    self.attachment.is_signed()):
                return 'reload_and_check'
            return 'check'
        return ''

    @fields.depends('digital_signature_required')
    def attachment_ok(self):
        res = super(DocumentRequestLine, self).attachment_ok()
        if not self.digital_signature_required:
            return res
        return res and (self.attachment and self.attachment.is_signed())

    @classmethod
    def update_electronic_signature_status(cls, request_lines):
        Attachment = Pool().get('ir.attachment')
        to_update = {}
        for line in request_lines:
            if not (line.digital_signature_required and line.attachment):
                continue
            has_signature_request = \
                line.attachment.has_signature_transaction_request()
            if has_signature_request and not line.attachment.is_signed():
                to_update[line] = line.attachment
        if to_update:
            Attachment.get_electronic_signature_transaction_info(
                to_update.values())
        to_receive = []
        for line, attachment in to_update.iteritems():
            if attachment.is_signed() and not \
                    line.reception_date:
                to_receive.append(line)
        if to_receive:
            cls.write(to_receive, {'reception_date': utils.today()})

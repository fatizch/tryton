# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.modules.coog_core import fields
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, Bool

from trytond.modules.coog_core import utils
from trytond.modules.offered.extra_data import with_extra_data

__all__ = [
    'DocumentDescription',
    'OfferedDocumentDescription',
    'DocumentRequestLine',
    ]


class DocumentDescription(metaclass=PoolMeta):
    __name__ = 'document.description'

    digital_signature_required = fields.Boolean('Digital Signature Required',
        states={'invisible': ~Eval('reception_requires_attachment')},
        depends=['reception_requires_attachment'])
    signature_configuration = fields.Many2One(
        'document.signature.configuration', 'Signature Configuration',
        ondelete="RESTRICT",
        states={'invisible': ~Eval('digital_signature_required')},
        depends=['digital_signature_required'])
    signature_credential = fields.Many2One(
        'document.signature.credential', 'Signature Credential',
        ondelete="RESTRICT",
        states={'invisible': ~Eval('digital_signature_required')},
        depends=['digital_signature_required'])

    @fields.depends('digital_signature_required',
        'reception_requires_attachment', 'signature_configuration',
        'signature_credential')
    def on_change_reception_requires_attachment(self):
        if not self.reception_requires_attachment:
            self.digital_signature_required = False
            self.signature_configuration = None
            self.signature_credential = None


class OfferedDocumentDescription(with_extra_data(['signature']),
        metaclass=PoolMeta):
    __name__ = 'document.description'

    @classmethod
    def __setup__(cls):
        super(DocumentDescription, cls).__setup__()
        cls.extra_data.states = {
            'invisible': ~Eval('digital_signature_required')}
        cls.extra_data.depends = ['digital_signature_required']

    @fields.depends('extra_data', 'signature_configuration')
    def on_change_signature_configuration(self):
        self.extra_data = {}
        if self.signature_configuration:
            for cur_extra_data in self.signature_configuration.extra_data_def:
                self.extra_data[cur_extra_data.name] = None

    @fields.depends('extra_data')
    def on_change_reception_requires_attachment(self):
        super(OfferedDocumentDescription,
            self).on_change_reception_requires_attachment()
        if not self.reception_requires_attachment:
            self.extra_data = {}


class DocumentRequestLine(metaclass=PoolMeta):
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
            Attachment.update_electronic_signature_transaction_info(
                list(to_update.values()))
        to_receive = []
        for line, attachment in to_update.items():
            if attachment.is_signed() and not \
                    line.reception_date:
                to_receive.append(line)
        if to_receive:
            cls.write(to_receive, {'reception_date': utils.today()})

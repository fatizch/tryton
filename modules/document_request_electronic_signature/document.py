# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict
from io import BytesIO
from PyPDF2 import PdfFileMerger, PdfFileReader, utils as PyPDF2utils

from trytond.i18n import gettext
from trytond.modules.coog_core import fields
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, Bool, Or
from trytond.model.exceptions import ValidationError

from trytond.modules.coog_core import utils, model

__all__ = [
    'DocumentDescription',
    'DocumentDescriptionPart',
    'DocumentSignatureCoordinate',
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
    sub_documents = fields.One2Many('document.description.part', 'parent_doc',
        'Composed Of', delete_missing=True,
        states={'invisible': ~Eval('digital_signature_required')},
        depends=['digital_signature_required'])
    signature_coordinates = fields.One2Many(
        'document.description.signature.coordinate', 'doc_desc',
        'Signature Coordinates', delete_missing=True,
        states={'invisible': ~Eval('digital_signature_required')},
        depends=['digital_signature_required'])

    @fields.depends('digital_signature_required',
        'reception_requires_attachment', 'signature_configuration',
        'signature_credential', 'sub_documents')
    def on_change_reception_requires_attachment(self):
        if not self.reception_requires_attachment:
            self.digital_signature_required = False
            self.signature_configuration = None
            self.signature_credential = None
            self.sub_documents = []

    def init_signature(self, report=None, attachment=None, from_object=None):
        if not self.digital_signature_required:
            return
        signer = ((report.get('party') or report.get('origin')
                or report.get('resource'))
            if report else attachment.resource).get_contact()
        if not report and attachment:
            report = {
                'report_name': attachment.name,
                'data': attachment.data,
                }
        report['coordinates'] = []
        for coordinate in self.signature_coordinates:
            report['coordinates'].append({
                   'page': coordinate.signature_page,
                   'coordinate_x': coordinate.signature_coordinate_x,
                   'coordinate_y': coordinate.signature_coordinate_y,
                    })
        # No need to try an electronic signature if we can't go through
        if signer and signer.email and (signer.mobile or signer.phone):
            report['signers'] = [signer]
            Signature = Pool().get('document.signature')
            Signature.request_transaction(report, attachment,
                config=self.signature_configuration,
                credential=self.signature_credential,
                from_object=from_object)


class DocumentDescriptionPart(model.CoogSQL, model.CoogView):
    'Document Description Part'

    __name__ = 'document.description.part'

    sequence = fields.Integer('Sequence')
    parent_doc = fields.Many2One('document.description', 'Parent Document',
        required=True, select=True, ondelete='CASCADE')
    doc = fields.Many2One('document.description', 'Document Desc',
        required=True, select=True, ondelete='RESTRICT')

    @classmethod
    def __setup__(cls):
        super(DocumentDescriptionPart, cls).__setup__()
        cls._order = [
            ('sequence', 'ASC'),
            ]


class DocumentSignatureCoordinate(model.CoogSQL, model.CoogView):
    'Document Signature Coordinate'

    __name__ = 'document.description.signature.coordinate'

    doc_desc = fields.Many2One('document.description', 'Document Description',
        required=True, select=True, ondelete='CASCADE')
    signature_coordinate_x = fields.Integer(
        'Horizontal signature coordinate', required=True)
    signature_coordinate_y = fields.Integer(
        'Vertical signature coordinate', required=True)
    signature_page = fields.Integer('Signature page', help='The page on which '
        'the signature must appear. 1 is the first and -1 is the last',
        required=True)


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
        attachment_data_readonly = cls.attachment_data.states.get('readonly',
            False) if cls.attachment_data.states else False
        cls.attachment_data.states = {'readonly': Or(attachment_data_readonly,
            Bool(Eval('digital_signature_required')))}
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
    def link_to_attachments(cls, requests, attachments):
        requests_to_save = super(DocumentRequestLine,
            cls).link_to_attachments(requests, attachments)
        attachments = []
        attachments_grouped = defaultdict(list)
        for request in [r for r in requests if r.document_desc]:
            attachments_grouped[request.document_desc] = ([request.attachment]
                if request.attachment and request.attachment.data else [])

        for request in [r for r in requests
                if r.document_desc and r.document_desc.sub_documents
                and not r.attachment]:
            for doc in [s.doc for s in request.document_desc.sub_documents]:
                if len(attachments_grouped[doc]) == 1:
                    attachment = attachments_grouped[doc][0]
                    try:
                        # Checking it is a real pdf file
                        PdfFileReader(BytesIO(attachment.data))
                        attachments_grouped[request.document_desc].append(
                            attachment)
                    except PyPDF2utils.PdfReadError:
                        raise ValidationError(gettext(
                                'document_request_electronic_signature.'
                                'msg_pdf_not_valid',
                                name=attachment.name))

            if len(attachments_grouped[request.document_desc]) != len(
                    request.document_desc.sub_documents):
                continue
            merger = PdfFileMerger()
            for attachment in attachments_grouped[request.document_desc]:
                # Set import bookmarks to False to avoid crash.
                merger.append(BytesIO(attachment.data), import_bookmarks=False)
            content = BytesIO()
            merger.write(content)
            request.attachment_data = content.getvalue()
            request.attachment_name = '.pdf'
            merger.close()
            requests_to_save.append(request)
        return requests_to_save

    def new_attachment(self, value, name='attachment_data'):
        attachment = super(DocumentRequestLine, self).new_attachment(value,
            name)
        self.document_desc.init_signature(attachment=attachment,
            from_object=self)
        return attachment

    def format_signature_url(self, url):
        if self.contract:
            return self.contract.format_signature_url(url)
        return super(DocumentRequestLine, self).format_signature_url(url)

    def notify_signature_completed(self, signature):
        self.reception_date = utils.today()
        self.save()
        Event = Pool().get('event')
        Event.notify_events([self], 'signature_completed')

    def notify_signature_failed(self, signature):
        Event = Pool().get('event')
        Event.notify_events([self], 'signature_failed')

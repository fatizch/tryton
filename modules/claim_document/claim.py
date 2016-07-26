# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict

from trytond.pool import PoolMeta, Pool
from trytond.model import ModelView

from trytond.modules.cog_utils import fields
from trytond.modules.document_request.document import RemindableInterface


__metaclass__ = PoolMeta
__all__ = [
    'Claim',
    ]


class Claim(RemindableInterface):
    __name__ = 'claim'
    __metaclass__ = PoolMeta

    document_request_lines = fields.One2Many('document.request.line',
        'claim', 'Required Documents', delete_missing=True)
    document_request = fields.One2Many('document.request', 'needed_by',
        'Document Request')
    doc_received = fields.Function(
        fields.Boolean('All Documents Received',
            depends=['document_request_lines']),
        'on_change_with_doc_received')
    attachments = fields.One2Many('ir.attachment', 'resource', 'Attachments',
        target_not_required=True)

    @classmethod
    def __setup__(cls):
        super(Claim, cls).__setup__()
        cls._buttons.update({
                'button_generate_document_request': {},
                'generate_reminds_documents': {},
                })

    @fields.depends('document_request_lines')
    def on_change_with_doc_received(self, name=None):
        for doc in self.document_request_lines:
            if not doc.received:
                return False
        return True

    @classmethod
    @ModelView.button
    def button_generate_document_request(cls, claims):
        pool = Pool()
        DocumentRequest = pool.get('document.request')
        to_save = []
        for claim in claims:
            to_save.append(DocumentRequest(
                    needed_by=claim,
                    documents=[line.id for line in claim.document_request_lines
                        if not line.received]
                    ))
        DocumentRequest.save(to_save)

    def link_attachments_to_requests(self):
        Request = Pool().get('document.request')
        attachments_grouped = defaultdict(list)
        for attachment in self.attachments:
            attachments_grouped[attachment.document_desc].append(attachment)
        to_save = []
        for request in self.document_request_lines:
            if not (request.document_desc and
                    len(attachments_grouped[request.document_desc]) == 1):
                continue
            request.attachment = attachments_grouped[request.document_desc][0]
            request.reception_date = request.attachment.create_date.date()
            to_save.append(request)
        Request.save(to_save)

    @classmethod
    def get_calculated_required_documents(cls, claims):
        claims_args = {c: {
                'date': c.declaration_date,
                } for c in claims}
        documents_per_claim = {c: {} for c in claims}
        for claim, claim_args in claims_args.iteritems():
            delivered_services = [x for loss in claim.losses
                for x in loss.services]
            for delivered in delivered_services:
                args = claim_args.copy()
                delivered.init_dict_for_rule_engine(args)
                docs = delivered.benefit.calculate_required_documents(
                    args)
                documents_per_claim[claim].update(docs)
        return documents_per_claim

    @classmethod
    def fill_to_remind(cls, doc_per_objects, to_remind, objects,
            force_remind, remind_if_false):
        for claim in objects:
            documents = doc_per_objects[claim]
            for loss in claim.losses:
                for delivered in loss.services:
                    benefit = delivered.benefit
                    config = benefit.documents_rules[0] \
                        if benefit.documents_rules else None
                    for doc in claim.document_request_lines:
                        if cls.is_document_needed(config, documents, doc,
                                remind_if_false, force_remind):
                            to_remind[claim].append(doc)

    @classmethod
    def get_reminder_candidates_query(cls, tables):
        return tables['claim'].join(
            tables['document.request.line'],
            condition=(tables['document.request.line'].claim ==
                tables['claim'].id))

    @classmethod
    def get_reminder_group_by_clause(cls, tables):
        return [tables['claim'].id]

    @classmethod
    def get_reminder_where_clause(cls, tables):
        return (tables['claim'].status == 'open')

    @classmethod
    @ModelView.button
    def generate_reminds_documents(cls, claims):
        super(Claim, cls).generate_reminds_documents(claims)

    def get_doc_template_kind(self):
        res = super(Claim, self).get_doc_template_kind()
        res.append('claim')
        return res

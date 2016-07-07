# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict
from dateutil.relativedelta import relativedelta
from sql.operators import Concat
from sql import Cast

from trytond.pool import PoolMeta, Pool
from trytond.model import ModelView

from trytond.modules.cog_utils import fields, utils
from trytond.modules.document_request.document import RemindableInterface


__metaclass__ = PoolMeta
__all__ = [
    'Claim',
    ]


class Claim(RemindableInterface):
    __name__ = 'claim'
    __metaclass__ = PoolMeta

    document_request_lines = fields.One2Many('document.request.line',
        'for_object', 'Required Documents', delete_missing=True)
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
    def get_document_lines_to_remind(cls, claims, force_remind):
        DocRequestLine = Pool().get('document.request.line')
        remind_if_false = DocRequestLine.default_remind_fields()
        to_remind = defaultdict(list)
        documents_per_claim = cls.get_calculated_required_documents(claims)
        for claim in claims:
            documents = documents_per_claim[claim]
            for loss in claim.losses:
                for delivered in loss.services:
                    benefit = delivered.benefit
                    if not benefit.documents_rules:
                        continue
                    delay = benefit.documents_rules[0].reminder_delay
                    unit = benefit.documents_rules[0].reminder_unit
                    for doc in claim.document_request_lines:
                        if remind_if_false and all([getattr(doc, x, False)
                                for x in remind_if_false]):
                            continue
                    if not delay:
                        if not force_remind:
                            to_remind[claim].append(doc)
                        to_remind[claim].append(doc)
                    delta = relativedelta(days=+delay) if unit == 'day' else \
                        relativedelta(months=+delay)
                    if doc.document_desc.code not in documents.keys():
                        continue
                    doc_max_reminders = documents[
                        doc.document_desc.code]['max_reminders']
                    if force_remind and (utils.today() - delta <
                            doc.last_reminder_date or
                            (doc_max_reminders and
                                 doc.reminders_sent >= doc_max_reminders)):
                        continue
                    to_remind[claim].append(doc)
        return to_remind

    @classmethod
    def get_reminder_candidates_query(cls, tables):
        return tables['claim'].join(
            tables['document.request.line'],
            condition=(tables['document.request.line'].for_object == Concat(
                'claim,', Cast(tables['claim'].id, 'VARCHAR'))))

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

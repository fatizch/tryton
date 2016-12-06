# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict

from sql import Null
from sql.aggregate import Count
from sql.operators import NotIn

from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.model import ModelView

from trytond.modules.coog_core import fields
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
    hidden_waiting_requests = fields.Function(
        fields.Boolean('Hidden waiting requests'),
        'get_hidden_waiting_requests',
        searcher='search_hidden_waiting_requests')

    @classmethod
    def __setup__(cls):
        super(Claim, cls).__setup__()
        cls._buttons.update({
                'button_generate_document_request': {},
                'generate_reminds_documents': {},
                })

    @classmethod
    def get_hidden_waiting_requests(cls, claims, name):
        # This getter allows the user to know if there are request lines which
        # he is not allowed to view, and which are not yet received.
        pool = Pool()
        line = pool.get('document.request.line').__table__()
        allowed_document_descs = pool.get('document.description').search([])

        where_clause = line.claim.in_([x.id for x in claims]) & (
            line.reception_date == Null)
        if allowed_document_descs:
            where_clause &= NotIn(line.document_desc,
                [x.id for x in allowed_document_descs])
        else:
            where_clause &= line.document_desc == Null

        cursor = Transaction().connection.cursor()
        cursor.execute(*line.select(line.claim,
                where=where_clause,
                group_by=[line.claim],
                having=Count(line.id) > 0))

        result = {x.id: False for x in claims}
        for claim_id, in cursor.fetchall():
            result[claim_id] = True
        return result

    @classmethod
    def search_hidden_waiting_requests(cls, name, clause):
        pool = Pool()
        line = pool.get('document.request.line').__table__()
        allowed_document_descs = pool.get('document.description').search([])

        expected = (clause[1] == '=' and clause[2] is True) or (
            clause[1] == '!=' and clause[2] is False)
        if expected:
            having_clause = Count(line.id) > 0
        else:
            having_clause = Count(line.id) == 0

        where_clause = line.reception_date == Null
        if allowed_document_descs:
            where_clause &= NotIn(line.document_desc, [x.id for x in
                    allowed_document_descs])
        else:
            where_clause &= line.document_desc == Null

        return [('id', 'in', line.select(line.claim,
                    where=where_clause,
                    group_by=[line.claim],
                    having=having_clause))]

    @fields.depends('document_request_lines', 'hidden_waiting_requests')
    def on_change_with_doc_received(self, name=None):
        return not self.hidden_waiting_requests and all(
            (x.received for x in self.document_request_lines))

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
            force_remind, remind_if_false, treatment_date):
        for claim in objects:
            documents = doc_per_objects[claim]
            for loss in claim.losses:
                for delivered in loss.services:
                    benefit = delivered.benefit
                    config = benefit.documents_rules[0] \
                        if benefit.documents_rules else None
                    for doc in claim.document_request_lines:
                        if cls.is_document_needed(config, documents, doc,
                                remind_if_false, force_remind, treatment_date):
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
    def generate_reminds_documents(cls, claims,
            treatment_date=None):
        super(Claim, cls).generate_reminds_documents(claims,
            treatment_date)

    def get_doc_template_kind(self):
        res = super(Claim, self).get_doc_template_kind()
        res.append('claim')
        return res

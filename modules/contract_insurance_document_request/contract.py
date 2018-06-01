# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from itertools import groupby
from collections import defaultdict

from sql import Null
from sql.aggregate import Count
from sql.operators import NotIn

from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from trytond.pyson import Eval
from trytond.model import ModelView

from trytond.modules.coog_core import fields
from trytond.modules.document_request.document import RemindableInterface


__all__ = [
    'Contract',
    ]


class Contract(RemindableInterface):
    __name__ = 'contract'
    __metaclass__ = PoolMeta

    attachments = fields.One2Many('ir.attachment', 'resource', 'Attachments',
        delete_missing=True, target_not_required=True)
    doc_received = fields.Function(
        fields.Boolean('All Documents Received'),
        'on_change_with_doc_received')
    document_request_lines = fields.One2Many('document.request.line',
        'contract', 'Documents',
        states={'readonly': Eval('status') != 'quote'},
        depends=['status'], delete_missing=True, target_not_required=True)
    hidden_waiting_request_lines = fields.Function(
        fields.Many2Many('document.request.line', None, None,
            'Hidden Waiting Request Lines'),
        'get_hidden_waiting_request_lines')
    hidden_waiting_requests = fields.Function(
        fields.Boolean('Hidden waiting requests'),
        'get_hidden_waiting_requests',
        searcher='search_hidden_waiting_requests')

    @classmethod
    def __setup__(cls):
        super(Contract, cls).__setup__()
        cls._error_messages.update({
                'missing_required_document':
                'Some required documents are missing.',
                'non_conform_documents':
                'Some required documents are not conform.',
                })
        cls._buttons.update({
                'generate_reminds_documents': {}
                })

    @classmethod
    def functional_skips_for_duplicate(cls):
        return (super(Contract, cls).functional_skips_for_duplicate() |
            set(['attachments']))

    @fields.depends('document_request_lines', 'hidden_waiting_requests')
    def on_change_with_doc_received(self, name=None):
        return not self.hidden_waiting_requests and all(
            (x.received for x in self.document_request_lines))

    @classmethod
    def _calculate_methods(cls, product):
        return super(Contract, cls)._calculate_methods(product) + [('contract',
                'init_subscription_document_request')]

    @classmethod
    def get_calculated_required_documents(cls, contracts):
        documents_per_contract = {c: {} for c in contracts}
        for contract in contracts:
            ctr_args = {
                'date': contract.start_date,
                'appliable_conditions_date': contract.appliable_conditions_date,
                }
            contract.init_dict_for_rule_engine(ctr_args)
            product_docs = contract.product.calculate_required_documents(
                ctr_args)
            documents_per_contract[contract].update(product_docs)
            for option in contract.covered_element_options + contract.options:
                if option.status != 'active':
                    continue
                args = {
                    'date': contract.start_date,
                    'appliable_conditions_date':
                    contract.appliable_conditions_date,
                    }
                option.init_dict_for_rule_engine(args)
                option_docs = option.coverage.calculate_required_documents(
                    args)
                documents_per_contract[contract].update(option_docs)
        return documents_per_contract

    @classmethod
    def get_hidden_waiting_request_lines(cls, contracts, name):
        # This getter allows the user to know if there are request lines which
        # he is not allowed to view, and which are not yet received.
        pool = Pool()
        line = pool.get('document.request.line').__table__()
        allowed_document_descs = pool.get('document.description').search([])

        where_clause = line.contract.in_([x.id for x in contracts]) & (
            line.reception_date == Null)
        if allowed_document_descs:
            where_clause &= NotIn(line.document_desc, [x.id for x in
                    allowed_document_descs])
        else:
            where_clause &= line.document_desc == Null

        cursor = Transaction().connection.cursor()
        cursor.execute(*line.select(line.id, line.contract,
                where=where_clause,
                group_by=[line.contract, line.id],
                having=Count(line.id) > 0))

        result = {x.id: [] for x in contracts}
        for line_id, contract_id, in cursor.fetchall():
            result[contract_id].append(line_id)
        return result

    @classmethod
    def get_hidden_waiting_requests(cls, contracts, name):
        return {c.id: bool(c.hidden_waiting_request_lines) for c in contracts}

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

        return [('id', 'in', line.select(line.contract,
                    where=where_clause,
                    group_by=[line.contract],
                    having=having_clause))]

    def init_subscription_document_request(self):
        if self.status != 'quote':
            return
        pool = Pool()
        DocumentRequestLine = pool.get('document.request.line')
        DocumentDesc = pool.get('document.description')
        documents = self.get_calculated_required_documents([self])[self]
        with Transaction().set_context(remove_document_desc_filter=True):
            rule_doc_descs_by_code = {x.code: x for x in
                DocumentDesc.search([('code', 'in', documents.keys())])}
            existing_document_desc_code = [request.document_desc.code
                for request in DocumentRequestLine.search([
                    ('for_object', '=', str(self))])]
        to_save = []
        for code, rule_result_values in documents.iteritems():
            if code in existing_document_desc_code:
                existing_document_desc_code.remove(code)
                continue
            line = DocumentRequestLine()
            line.document_desc = rule_doc_descs_by_code[code]
            line.for_object = '%s,%s' % (self.__name__, self.id)
            line.contract = self
            for k, v in rule_result_values.iteritems():
                setattr(line, k, v)
            to_save.append(line)
        if to_save:
            DocumentRequestLine.save(to_save)
        to_delete = []
        for request in self.document_request_lines:
            if (request.document_desc.code in existing_document_desc_code and
                    not request.send_date and not request.reception_date):
                to_delete.append(request)
        DocumentRequestLine.delete(to_delete)

    def link_attachments_to_requests(self):
        attachments_grouped = defaultdict(list)
        for attachment in self.attachments:
            attachments_grouped[attachment.document_desc].append(attachment)
        for request in self.document_request_lines:
            if not (request.document_desc and
                    len(attachments_grouped[request.document_desc]) == 1):
                continue
            request.attachment = attachments_grouped[request.document_desc][0]
            request.save()

    @classmethod
    def update_contract_after_import(cls, contracts):
        super(Contract, cls).update_contract_after_import(contracts)
        for contract in contracts:
            contract.init_subscription_document_request()
            contract.link_attachments_to_requests()

    def check_required_documents(self, only_blocking=False,
            only_authorized=False):
        missing = False
        non_conform = False
        request_lines = (self.document_request_lines
            + self.hidden_waiting_request_lines)
        if only_authorized:
            user = Transaction().user
            filtered_lines = []
            for line in request_lines:
                if not line.document_desc or not line.document_desc.groups:
                    filtered_lines.append(line)
                    continue
                for group in line.document_desc.groups:
                    if user in group.users:
                        filtered_lines.append(line)
                        break
            request_lines = filtered_lines
        if not only_blocking and not self.doc_received:
            missing = True
        elif not all((x.received for x in request_lines
                if x.blocking)):
            missing = True
        elif not only_blocking and not all((line.attachment.is_conform
                for line in request_lines
                if line.attachment)):
            non_conform = True
        elif not all((line.attachment.is_conform
                for line in request_lines
                if line.blocking and line.attachment)):
            non_conform = True
        if missing:
            self.raise_user_error('missing_required_document')
        if non_conform:
            self.raise_user_error('non_conform_documents')

    def before_activate(self):
        self.check_required_documents(only_blocking=True)
        super(Contract, self).before_activate()

    @classmethod
    def get_reminder_candidates_query(cls, tables):
        return tables['contract'].join(
            tables['document.request.line'],
            condition=(tables['document.request.line'].contract ==
                tables['contract'].id))

    @classmethod
    def get_reminder_group_by_clause(cls, tables):
        return [tables['contract'].id]

    @classmethod
    def get_reminder_where_clause(cls, tables):
        return tables['contract'].status.in_(['quote'])

    @classmethod
    def fill_to_remind(cls, doc_per_objects, to_remind, objects,
            force_remind, remind_if_false, treatment_date):
        def keyfunc(x):
            return x.product

        for product, contracts in groupby(objects, key=keyfunc):
            config = product.document_rules[0] if \
                product.document_rules else None
            for contract in contracts:
                documents = doc_per_objects[contract]
                for doc in contract.document_request_lines:
                    if cls.is_document_needed(config, documents, doc,
                            remind_if_false, force_remind, treatment_date):
                        to_remind[contract].append(doc)

    @classmethod
    @ModelView.button
    def generate_reminds_documents(cls, contracts,
            treatment_date=None):
        super(Contract, cls).generate_reminds_documents(contracts,
            treatment_date)

# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from itertools import groupby
from collections import defaultdict

from trytond.pool import Pool, PoolMeta
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
        delete_missing=False, target_not_required=True)
    doc_received = fields.Function(
        fields.Boolean('All Documents Received'),
        'on_change_with_doc_received')
    document_request_lines = fields.One2Many('document.request.line',
        'contract', 'Documents',
        states={'readonly': Eval('status') != 'quote'},
        depends=['status'], delete_missing=True)

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

    @fields.depends('document_request_lines')
    def on_change_with_doc_received(self, name=None):
        return all((x.received for x in self.document_request_lines))

    @classmethod
    def get_calculated_required_documents(cls, contracts):
        contracts_args = {c: {
                'date': c.start_date,
                'appliable_conditions_date': c.appliable_conditions_date,
                } for c in contracts}
        documents_per_contract = {c: {} for c in contracts}
        for contract, contract_args in contracts_args.iteritems():
            product_docs = contract.product.calculate_required_documents(
                contract_args)
            documents_per_contract[contract].update(product_docs)
            for option in contract.covered_element_options + contract.options:
                if option.status != 'active':
                    continue
                args = contract_args.copy()
                option.init_dict_for_rule_engine(args)
                option_docs = option.coverage.calculate_required_documents(
                    args)
                documents_per_contract[contract].update(option_docs)
        return documents_per_contract

    def init_subscription_document_request(self):
        pool = Pool()
        DocumentRequestLine = pool.get('document.request.line')
        DocumentDesc = pool.get('document.description')
        documents = self.get_calculated_required_documents([self])[self]

        existing_document_desc_code = [request.document_desc.code
            for request in self.document_request_lines]
        rule_doc_descs_by_code = {x.code: x for x in
            DocumentDesc.search([('code', 'in', documents.keys())])}
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

    def check_required_documents(self, only_blocking=False):
        missing = False
        non_conform = False
        if not only_blocking and not self.doc_received:
            missing = True
        elif not all((x.received for x in self.document_request_lines
                if x.blocking)):
            missing = True
        elif not only_blocking and not all((line.attachment.is_conform
                for line in self.document_request_lines
                if line.attachment)):
            non_conform = True
        elif not all((line.attachment.is_conform
                for line in self.document_request_lines
                if line.blocking and line.attachment)):
            non_conform = True
        if missing:
            self.raise_user_error('missing_required_document')
        if non_conform:
            self.raise_user_error('non_conform_documents')

    def before_activate(self):
        self.check_required_documents()
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

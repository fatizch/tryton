# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from itertools import groupby
from collections import defaultdict
from dateutil.relativedelta import relativedelta
from sql.operators import Concat
from sql import Cast

from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.model import ModelView

from trytond.modules.cog_utils import fields, utils
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
        'for_object', 'Documents',
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
        for code, rule_result_values in documents.iteritems():
            if code in existing_document_desc_code:
                existing_document_desc_code.remove(code)
                continue
            line = DocumentRequestLine()
            line.document_desc = rule_doc_descs_by_code[code]
            line.for_object = '%s,%s' % (self.__name__, self.id)
            for k, v in rule_result_values.iteritems():
                setattr(line, k, v)
            line.save()
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
            condition=(tables['document.request.line'].for_object == Concat(
                'contract,', Cast(tables['contract'].id, 'VARCHAR'))))

    @classmethod
    def get_reminder_group_by_clause(cls, tables):
        return [tables['contract'].id]

    @classmethod
    def get_reminder_where_clause(cls, tables):
        return tables['contract'].status.in_(['quote'])

    @classmethod
    def get_document_lines_to_remind(cls, contracts, force_remind):
        DocRequestLine = Pool().get('document.request.line')
        remind_if_false = DocRequestLine.default_remind_fields()
        def keyfunc(x): return x.product

        contracts = sorted(contracts, key=keyfunc)
        to_remind = defaultdict(list)
        documents_per_contract = cls.get_calculated_required_documents(
            contracts)

        for product, contracts in groupby(contracts, key=keyfunc):
            if not product.document_rules:
                continue
            delay = product.document_rules[0].reminder_delay
            unit = product.document_rules[0].reminder_unit
            for contract in contracts:
                documents = documents_per_contract[contract]
                for doc in contract.document_request_lines:
                    if remind_if_false and all([getattr(doc, x, False) for x in
                            remind_if_false]):
                        continue
                    if not delay:
                        if not force_remind:
                            to_remind[contract].append(doc)
                        continue
                    delta = relativedelta(days=+delay) if unit == 'day' else \
                        relativedelta(months=+delay)
                    doc_max_reminders = documents[
                        doc.document_desc.code]['max_reminders']
                    if force_remind and (utils.today() - delta <
                            doc.last_reminder_date or
                            (doc_max_reminders and
                                 doc.reminders_sent >= doc_max_reminders)):
                        continue
                    to_remind[contract].append(doc)
        return to_remind

    @classmethod
    @ModelView.button
    def generate_reminds_documents(cls, contracts):
        super(Contract, cls).generate_reminds_documents(contracts)

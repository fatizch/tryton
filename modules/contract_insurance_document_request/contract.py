# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from itertools import groupby
from collections import defaultdict
from sql import Null
from sql.aggregate import Count
from sql.operators import NotIn
from trytond.i18n import gettext
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from trytond.pyson import Eval
from trytond.model import ModelView
from trytond.model.exceptions import ValidationError

from trytond.modules.coog_core import fields
from trytond.modules.document_request.document import RemindableInterface
from trytond.modules.contract_insurance.contract import COVERED_READ_ONLY
from trytond.modules.contract_insurance.contract import COVERED_STATUS_DEPENDS


__all__ = [
    'Contract',
    'CoveredElement',
    ]


class Contract(RemindableInterface, metaclass=PoolMeta):
    __name__ = 'contract'

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
        return super(Contract, cls)._calculate_methods(product) + [
            ('contract', 'init_subscription_document_request')]

    @classmethod
    def get_calculated_required_documents(cls, contracts):
        documents_per_contract = {c: {} for c in contracts}
        for contract in contracts:
            ctr_args = {
                'date': contract.start_date,
                'appliable_conditions_date': contract.appliable_conditions_date,
                }
            contract.init_dict_for_rule_engine(ctr_args)
            product_docs = {(contract, contract.product):
                contract.product.calculate_required_documents(ctr_args)}
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
                if option.covered_element:
                    for_object = option.covered_element
                else:
                    for_object = contract
                documents_per_contract[contract].update({(for_object, option):
                    option.coverage.calculate_required_documents(args)})
        return documents_per_contract

    @classmethod
    def get_hidden_waiting_request_lines(cls, instances, name):
        Line = Pool().get('document.request.line')
        return Line.get_hidden_waiting_request_lines(instances, 'contract')

    def get_request_lines(self, with_hidden=True, only_pending=True):
        lines = self.document_request_lines
        if with_hidden:
            lines += self.hidden_waiting_request_lines
        return [l for l in lines if not only_pending or not l.received]

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
        DocumentDescription = pool.get('document.description')
        documents = self.get_calculated_required_documents([self])[self]
        rule_codes_by_for_object = defaultdict(set)
        existing_codes_by_for_object = defaultdict(list)
        with Transaction().set_context(remove_document_desc_filter=True):
            all_codes = {x.code: x.id for x in DocumentDescription.search([])}
            existing_lines = DocumentRequestLine.search(
                [('contract', '=', self)],
                order=[('for_object', 'ASC')])

        for for_object, grouped_lines in groupby(existing_lines,
                    key=lambda x: x.for_object):
            existing_codes_by_for_object[for_object] = [
                x.document_desc.code for x in grouped_lines]

        for (for_object, rule_source), result in documents.items():
            rule_codes = result.keys()
            rule_codes_by_for_object[for_object] |= set(rule_codes)

        to_save = []
        for (for_object, rule_source), rule_result in documents.items():
            for code, rule_result_values in rule_result.items():
                if code in existing_codes_by_for_object[for_object]:
                    continue
                line = DocumentRequestLine()
                line.document_desc = all_codes[code]
                line.contract = self
                line.for_object = str(for_object)
                for k, v in rule_result_values.items():
                    setattr(line, k, v)
                line.on_change_document_desc()
                line.added_manually = False
                to_save.append(line)
        if to_save:
            DocumentRequestLine.save(to_save)
            to_confirm = [x for x in to_save
                if x.data_status == 'waiting'
                and x.document_desc
                and not x.document_desc.extra_data_def]
            if to_confirm:
                DocumentRequestLine.confirm_attachment(to_confirm)

        # handle case a document is not required because
        # the rules now return a different result or
        # the configuration has changed
        to_delete = []
        with Transaction().set_context(remove_document_desc_filter=True):
            for request in self.document_request_lines:
                if request.added_manually is True:
                    continue
                rule_codes = rule_codes_by_for_object[request.for_object]
                if request.document_desc.code not in rule_codes \
                        and not request.send_date and not \
                        request.reception_date:
                    to_delete.append(request)
            if to_delete:
                DocumentRequestLine.delete(to_delete)

    def link_attachments_to_requests(self):
        DocumentRequestLine = Pool().get('document.request.line')
        requests = DocumentRequestLine.link_to_attachments(
            self.document_request_lines, self.attachments)
        if requests:
            DocumentRequestLine.save(requests)

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
            raise ValidationError(gettext(
                    'contract_insurance_document_request'
                    '.msg_missing_required_document'))
        if non_conform:
            raise ValidationError(gettext(
                    'contract_insurance_document_request'
                    '.msg_non_conform_documents'))

    def before_activate(self):
        super(Contract, self).before_activate()
        self.check_required_documents(only_blocking=True)

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


class CoveredElement(metaclass=PoolMeta):
    __name__ = 'contract.covered_element'

    document_request_lines = fields.One2Many('document.request.line',
        'for_object', 'Requested Documents',
        states={'readonly': COVERED_READ_ONLY},
        depends=COVERED_STATUS_DEPENDS, delete_missing=True,
        target_not_required=True)
    hidden_waiting_request_lines = fields.Function(
        fields.Many2Many('document.request.line', None, None,
            'Hidden Waiting Request Lines'),
        'get_hidden_waiting_request_lines')

    def get_request_lines(self, with_hidden=True, only_pending=True):
        lines = list(self.document_request_lines) + list(
            self.hidden_waiting_request_lines)
        return [l for l in lines if not only_pending or not l.received]

    @classmethod
    def get_hidden_waiting_request_lines(cls, instances, name):
        Line = Pool().get('document.request.line')
        return Line.get_hidden_waiting_request_lines(instances, 'for_object')

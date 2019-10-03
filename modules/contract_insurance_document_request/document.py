# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Cast
from sql.functions import Substring
from collections import defaultdict

from trytond import backend
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.pyson import Eval

from trytond.modules.coog_core import fields


__all__ = [
    'DocumentRequest',
    'DocumentRequestLine',
    'DocumentReception',
    'ReceiveDocument',
    ]


class DocumentRequestLine(metaclass=PoolMeta):
    __name__ = 'document.request.line'

    contract = fields.Many2One('contract', 'Contract',
        ondelete='CASCADE', select=True)

    @classmethod
    def __setup__(cls):
        super(DocumentRequestLine, cls).__setup__()
        or_clause = cls.attachment.domain[0]
        assert or_clause[0] == 'OR'
        or_clause.append(('resource.id', '=', Eval('contract'), 'contract'))
        cls.attachment.depends.append('contract')

    def get_attachment_possible_resources(self):
        res = super(DocumentRequestLine,
            self).get_attachment_possible_resources()
        res.append(str(self.contract))
        return res

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        table_handler = TableHandler(cls, module_name)
        cursor = Transaction().connection.cursor()
        migrate = False
        if not table_handler.column_exist('contract'):
            migrate = True
        # Migrate from 1.8 : add field relation to a contract
        super(DocumentRequestLine, cls).__register__(module_name)
        if migrate:
            table = cls.__table__()
            cursor.execute(*table.update(
                    columns=[table.contract],
                    values=[Cast(Substring(table.for_object,
                                len('contract,') + 1),
                            cls.contract.sql_type().base)],
                    where=(table.for_object.like('contract,%'))
                    ))

    @classmethod
    def update_values_from_target(cls, data_dict):
        super(DocumentRequestLine, cls).update_values_from_target(data_dict)
        for target, values in data_dict.items():
            if not target or not target.startswith('contract,'):
                continue
            contract_id = int(target.split(',')[1])
            for value in values:
                if 'contract' in value:
                    continue
                value['contract'] = contract_id

    @fields.depends('contract', 'for_object')
    def on_change_contract(self):
        if self.for_object is None:
            self.for_object = self.contract

    @classmethod
    def for_object_models(cls):
        return super(DocumentRequestLine, cls).for_object_models() + \
            ['contract', 'contract.covered_element']

    @classmethod
    def link_to_attachments(cls, requests, attachments):
        requests_to_save = []
        attachments_grouped = defaultdict(list)
        for attachment in [a for a in attachments if a.status != 'invalid']:
            attachments_grouped[attachment.document_desc].append(attachment)
        for request in requests:
            if not (request.document_desc and
                    attachments_grouped[request.document_desc]):
                continue
            request.attachment = attachments_grouped[request.document_desc][0]
            requests_to_save.append(request)
        return requests_to_save

    def get_object_to_print(self, model):
        if model == 'contract':
            return self.contract
        return super(DocumentRequestLine, self).get_object_to_print(model)

    def get_reference_object_for_edm(self):
        if self.contract:
            return self.contract
        return super(DocumentRequestLine, self).get_reference_object_for_edm()


class DocumentRequest(metaclass=PoolMeta):
    __name__ = 'document.request'

    @classmethod
    def __setup__(cls):
        super(DocumentRequest, cls).__setup__()
        cls.needed_by.selection.append(
            ('contract', 'Contract'))


class DocumentReception(metaclass=PoolMeta):
    __name__ = 'document.reception'

    contract = fields.Many2One('contract', 'Contract', ondelete='SET NULL',
        domain=[('id', 'in', Eval('possible_contracts'))],
        states={'readonly': Eval('state', '') == 'done',
            'invisible': ~Eval('party')},
        depends=['party', 'possible_contracts', 'state'])
    possible_contracts = fields.Function(
        fields.Many2Many('contract', None, None, 'Possible Contracts'),
        'on_change_with_possible_contracts')

    @classmethod
    def __setup__(cls):
        super(DocumentReception, cls).__setup__()
        cls.request.domain = ['OR', cls.request.domain, [
                ('contract', '=', Eval('contract')),
                ('reception_date', '=', None),
                ('attachment', '=', None),
                ('document_desc', '=', Eval('document_desc'))]]
        cls.request.depends += ['contract', 'document_desc']

    @fields.depends('party')
    def on_change_with_possible_contracts(self, name=None):
        if not self.party:
            return []
        pool = Pool()
        Contract = pool.get('contract')
        CoveredElement = pool.get('contract.covered_element')
        contracts = set()
        contracts |= {x.id for x in Contract.search([
                    ('subscriber', '=', self.party.id)])}
        contracts |= {x.contract.id for x in CoveredElement.search([
                    ('party', '=', self.party.id)])}
        return list(contracts)


class ReceiveDocument(metaclass=PoolMeta):
    __name__ = 'document.receive'

    def get_possible_objects_from_document(self, document):
        objects = super(ReceiveDocument,
            self).get_possible_objects_from_document(document)
        if document.contract:
            objects = [document.contract]
        else:
            objects += list(document.possible_contracts)
        return objects

    def get_object_filtering_clause(self, record):
        if record.__name__ == 'contract':
            return [('contract', '=', record.id)]
        return super(ReceiveDocument, self).get_object_filtering_clause(
            record)

    def set_object_line(self, line, per_object):
        if line.contract:
            per_object[line.contract].append(line)
        else:
            super(ReceiveDocument, self).set_object_line(line, per_object)

# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Cast, Null
from sql.functions import Substring
from sql.aggregate import Count
from sql.operators import NotIn
from collections import defaultdict

from trytond import backend
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.pyson import Eval

from trytond.modules.coog_core import fields, model, coog_string


__all__ = [
    'DocumentRequest',
    'DocumentRequestLine',
    'DocumentDescription',
    'DocumentDescriptionProduct',
    'DocumentReception',
    'ReceiveDocument',
    ]


class DocumentRequestLine(metaclass=PoolMeta):
    __name__ = 'document.request.line'

    contract = fields.Many2One('contract', 'Contract',
        ondelete='CASCADE', select=True)
    product = fields.Function(
        fields.Many2One('offered.product', 'Product'),
        'on_change_with_product')

    @classmethod
    def __setup__(cls):
        super(DocumentRequestLine, cls).__setup__()
        or_clause = cls.attachment.domain[0]
        assert or_clause[0] == 'OR'
        or_clause.append(('resource.id', '=', Eval('contract'), 'contract'))
        cls.attachment.depends.append('contract')

        cls.document_desc.domain.append([
                'OR',
                [('products', '=', None)],
                [('products', '=', Eval('product'))]
                ])
        cls.document_desc.depends += ['product']

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
        if self.for_object is None and self.contract:
            self.for_object = self.contract
            self.for_object_selection = str(self.contract)

    @fields.depends('contract')
    def on_change_with_product(self, name=None):
        return self.contract.product.id if self.contract else None

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

    @classmethod
    def get_hidden_waiting_request_lines(cls, instances, var_name):
        # This getter allows the user to know if there are request lines which
        # he is not allowed to view, and which are not yet received.
        pool = Pool()
        line = cls.__table__()
        allowed_document_descs = pool.get('document.description').search([])

        if var_name == 'for_object':
            where_clause = getattr(line, var_name).in_(
                [str(x) for x in instances])
        else:
            where_clause = getattr(line, var_name).in_(
                [x.id for x in instances])
        where_clause &= (line.reception_date == Null)
        if allowed_document_descs:
            where_clause &= NotIn(line.document_desc, [x.id for x in
                    allowed_document_descs])
        else:
            where_clause &= line.document_desc == Null

        cursor = Transaction().connection.cursor()
        cursor.execute(*line.select(line.id, getattr(line, var_name),
                where=where_clause,
                group_by=[getattr(line, var_name), line.id],
                having=Count(line.id) > 0))

        result = {x.id: [] for x in instances}
        for line_id, _id, in cursor.fetchall():
            result[_id].append(line_id)
        return result

    @fields.depends('contract')
    def get_possible_objects(self):
        selection = super().get_possible_objects()
        if self.contract:
            selection.append((str(self.contract),
                coog_string.translate_label(self, 'contract')))
            for element in self.contract.covered_elements:
                selection.append((str(element), element.rec_name))
        return selection


class DocumentRequest(metaclass=PoolMeta):
    __name__ = 'document.request'

    @classmethod
    def __setup__(cls):
        super(DocumentRequest, cls).__setup__()
        cls.needed_by.selection.append(
            ('contract', 'Contract'))


class DocumentDescription(metaclass=PoolMeta):
    __name__ = 'document.description'

    products = fields.Many2Many('document.description-product', 'document_desc',
        'product', 'Product Filter', help='Used to filter document desc per '
        'product on request line for a contract. If not set will be available '
        'for all products')
    products_name = fields.Function(
        fields.Char('Products'), 'on_change_with_products_name')

    @fields.depends('products')
    def on_change_with_products_name(self, name=None):
        return ', '.join([p.rec_name for p in self.products])


class DocumentDescriptionProduct(model.CoogSQL):
    'Document Desc To Product Relation'

    __name__ = 'document.description-product'

    document_desc = fields.Many2One('document.description',
        'Document Description', ondelete='CASCADE', required=True, select=True)
    product = fields.Many2One('offered.product', 'Product', ondelete='CASCADE',
        required=True, select=True)


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

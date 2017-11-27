# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Cast
from sql.functions import Substring

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


class DocumentRequestLine:
    __metaclass__ = PoolMeta
    __name__ = 'document.request.line'

    contract = fields.Many2One('contract', 'Contract',
        ondelete='CASCADE', select=True)

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
        for target, values in data_dict.iteritems():
            if not target or not target.startswith('contract,'):
                continue
            contract_id = int(target.split(',')[1])
            for value in values:
                if 'contract' in value:
                    continue
                value['contract'] = contract_id

    @classmethod
    def for_object_models(cls):
        return super(DocumentRequestLine, cls).for_object_models() + \
            ['contract']

    def attachment_not_required(self):
        if self.contract:
            return not self.contract.product.reception_requires_attachment
        return super(DocumentRequestLine,
            self).get_for_object_attachment_required()


class DocumentRequest:
    __metaclass__ = PoolMeta
    __name__ = 'document.request'

    @classmethod
    def __setup__(cls):
        super(DocumentRequest, cls).__setup__()
        cls.needed_by.selection.append(
            ('contract', 'Contract'))


class DocumentReception:
    __metaclass__ = PoolMeta
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
        contracts |= {x.main_contract.id for x in CoveredElement.search([
                    ('party', '=', self.party.id)])}
        return list(contracts)


class ReceiveDocument:
    __metaclass__ = PoolMeta
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

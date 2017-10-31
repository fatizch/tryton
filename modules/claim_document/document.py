# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Cast
from sql.functions import Substring

from trytond.pool import PoolMeta, Pool
from trytond import backend
from trytond.pyson import Eval
from trytond.transaction import Transaction

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

    claim = fields.Many2One('claim', 'Claim', ondelete='CASCADE', select=True)
    claim_status = fields.Function(fields.Char('Claim Status'),
        'get_claim_status')

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        table_handler = TableHandler(cls, module_name)
        cursor = Transaction().connection.cursor()
        migrate = False
        # Migrate from 1.8 : add field relation to a claim
        if not table_handler.column_exist('claim'):
            migrate = True
        super(DocumentRequestLine, cls).__register__(module_name)
        if migrate:
            table = cls.__table__()
            cursor.execute(*table.update(
                    columns=[table.claim],
                    values=[Cast(Substring(table.for_object,
                                len('claim,') + 1),
                            cls.claim.sql_type().base)],
                    where=(table.for_object.like('claim,%'))
                    ))

    @classmethod
    def __post_setup__(cls):
        super(DocumentRequestLine, cls).__post_setup__()
        cls.set_fields_readonly_condition(Eval('claim_status') == 'closed',
            ['claim_status'], cls._get_skip_set_readonly_fields())

    @classmethod
    def _get_skip_set_readonly_fields(cls):
        return []

    def get_claim_status(self, name):
        if self.claim:
            return self.claim.status

    @classmethod
    def update_values_from_target(cls, data_dict):
        super(DocumentRequestLine, cls).update_values_from_target(data_dict)
        for target, values in data_dict.iteritems():
            if not target.startswith('claim,'):
                continue
            claim_id = int(target.split(',')[1])
            for value in values:
                if 'claim' in value:
                    continue
                value['claim'] = claim_id

    @fields.depends('claim', 'for_object')
    def on_change_claim(self):
        if self.for_object is None:
            self.for_object = self.claim

    @classmethod
    def for_object_models(cls):
        return super(DocumentRequestLine, cls).for_object_models() + \
            ['claim']


class DocumentRequest:
    __metaclass__ = PoolMeta
    __name__ = 'document.request'

    @classmethod
    def __setup__(cls):
        super(DocumentRequest, cls).__setup__()
        cls.needed_by.selection.append(('claim', 'Claim'))
        cls.needed_by.selection.append(
            ('claim.service', 'Claim Service'))


class DocumentReception:
    __metaclass__ = PoolMeta
    __name__ = 'document.reception'

    claim = fields.Many2One('claim', 'Claim', ondelete='SET NULL',
        domain=[('id', 'in', Eval('possible_claims'))],
        states={'readonly': Eval('state', '') == 'done',
            'invisible': ~Eval('party')},
        depends=['party', 'possible_claims', 'state'])
    possible_claims = fields.Function(
        fields.Many2Many('claim', None, None, 'Possible Claims'),
        'on_change_with_possible_claims')

    @classmethod
    def __setup__(cls):
        super(DocumentReception, cls).__setup__()
        cls.request.domain = ['OR', cls.request.domain, [
                ('claim', '=', Eval('claim')),
                ('reception_date', '=', None),
                ('attachment', '=', None),
                ('document_desc', '=', Eval('document_desc'))]]
        cls.request.depends += ['claim', 'document_desc']

    @fields.depends('party')
    def on_change_with_possible_claims(self, name=None):
        if not self.party:
            return []
        pool = Pool()
        Claim = pool.get('claim')
        claims = set()
        claims |= {x.id for x in Claim.search([
                    ('claimant', '=', self.party.id)])}
        return list(claims)


class ReceiveDocument:
    __metaclass__ = PoolMeta
    __name__ = 'document.receive'

    def get_possible_objects_from_document(self, document):
        objects = super(ReceiveDocument,
            self).get_possible_objects_from_document(document)
        if document.claim:
            objects = [document.claim]
        else:
            objects += list(document.possible_claims)
        return objects

    def get_object_filtering_clause(self, record):
        if record.__name__ == 'claim':
            return [('claim', '=', record.id)]
        return super(ReceiveDocument, self).get_object_filtering_clause(
            record)

    def set_object_line(self, line, per_object):
        if line.claim:
            per_object[line.claim].append(line)
        else:
            super(ReceiveDocument, self).set_object_line(line, per_object)
# -*- coding: utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool

from trytond.modules.coog_core import fields, coog_string, export

__all__ = [
    'RelationType',
    'PartyRelation',
    'PartyRelationAll',
    ]


class RelationType(export.ExportImportMixin):
    __name__ = 'party.relation.type'
    _func_key = 'code'

    code = fields.Char('Code', required=True)

    @fields.depends('code', 'name')
    def on_change_with_code(self):
        if self.code:
            return self.code
        return coog_string.slugify(self.name)

    @classmethod
    def _export_skips(cls):
        return super(RelationType, cls)._export_skips() | {'reverse'}


class PartyRelation(export.ExportImportMixin):
    __name__ = 'party.relation'
    _func_key = 'func_key'

    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    func_key = fields.Function(fields.Char('Functional Key'),
        'get_func_key', searcher='search_func_key')

    def get_func_key(self, name):
        return '%s|%s' % ((self.type.code, self.to.code))

    @classmethod
    def add_func_key(cls, values):
        pool = Pool()
        Party = pool.get('party.party')
        parties = Party.search_for_export_import(values['to'])
        party, = parties
        values['_func_key'] = '%s|%s' % ((values['type']['_func_key'],
                party.code))

    @classmethod
    def search_func_key(cls, name, clause):
        assert clause[1] == '='
        if '|' in clause[2]:
            operands = clause[2].split('|')
            if len(operands) == 2:
                rel_type, party_code = clause[2].split('|')
                return [('type.code', clause[1], rel_type),
                    ('to.code', clause[1], party_code)]
            else:
                return [('id', '=', None)]
        else:
            return ['OR',
                [('type.code',) + tuple(clause[1:])],
                [('to.code',) + tuple(clause[1:])],
                ]

    def get_rec_name(self, name):
        if self.type and self.to:
            return '%s %s %s' % (self.type.name, u'→', self.to.rec_name)
        return ''

    def get_summary_content(self, label, at_date=None, lang=None):
        return (None, '%s : %s' % (self.type.reverse.name, self.to.rec_name))


class PartyRelationAll(PartyRelation):
    __name__ = 'party.relation.all'

    def get_synthesis_rec_name(self, name):
        return '%s: %s' % (self.type.rec_name, self.to.rec_name)

    @classmethod
    def restore_history_before(cls, ids, datetime):
        Relation = Pool().get('party.relation')
        Relation._restore_history([x // 2 for x in ids], datetime, _before=True)

    @classmethod
    def _export_light(cls):
        return set(['type'])

    def export_json(self, skip_fields=None, already_exported=None,
            output=None, main_object=None, configuration=None):
        # Parity is used by tryton to know which direction of
        # the relationship is stored
        if not self.id % 2:
            return super(PartyRelationAll, self).export_json(skip_fields,
                already_exported, output, main_object, configuration)
        else:
            self.to.export_json(skip_fields, already_exported, output,
                main_object, configuration)

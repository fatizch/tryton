# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

from trytond.modules.coog_core import export, fields

__metaclass__ = PoolMeta
__all__ = [
    'Company',
    ]


class Company(export.ExportImportMixin):
    __name__ = 'company.company'
    _func_key = 'func_key'

    func_key = fields.Function(fields.Char('Functional Key'),
        'get_func_key', searcher='search_func_key')

    @classmethod
    def __setup__(cls):
        super(Company, cls).__setup__()
        cls.party.ondelete = 'RESTRICT'

    @classmethod
    def _export_light(cls):
        return super(Company, cls)._export_light() | {'currency'}

    def get_publishing_values(self):
        result = self.party.get_publishing_values()
        return result

    def get_rec_name(self, name):
        return self.party.name

    def get_func_key(self, name):
        return self.party.code

    @classmethod
    def search_func_key(cls, name, clause):
        return [('party.code',) + tuple(clause[1:])]

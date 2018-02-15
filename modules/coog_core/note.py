# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.modules.coog_core import export

__all__ = ['Note']


class Note(export.ExportImportMixin):
    'Note'
    __name__ = 'ir.note'
    _func_key = 'id'

    @classmethod
    def __setup__(cls):
        super(Note, cls).__setup__()
        cls._order = [('create_date', 'DESC')]

    @classmethod
    def add_func_key(cls, values):
        # importing a note will always create a new one
        # override add_func_key since it's required during import
        values['_func_key'] = 0

from trytond.pool import PoolMeta

from trytond.modules.cog_utils import export

__all__ = ['Note']
__metaclass__ = PoolMeta


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

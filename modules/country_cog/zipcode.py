from trytond.model import Unique
from trytond.pool import PoolMeta
from trytond.transaction import Transaction
from trytond import backend

from trytond.modules.cog_utils import export, utils

__metaclass__ = PoolMeta
__all__ = [
    'Zip',
    ]


class Zip(export.ExportImportMixin):
    __name__ = 'country.zip'
    _rec_name = 'zip'

    @classmethod
    def __setup__(cls):
        super(Zip, cls).__setup__()
        cls.zip.required = True
        cls.zip.select = True
        cls.city.required = True
        cls.city.select = True

        t = cls.__table__()
        # country_fr removes the 'zip_uniq' constraint
        # but there is apparently no way to prevent
        # its creation by overloading __setup__
        # or __register__ in country_fr
        if utils.is_module_installed('country_fr'):
            return
        cls._sql_constraints += [
            ('zip_uniq', Unique(t, t.zip, t.city, t.country),
                'This city and this zipcode already exist for this country!'),
            ]

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().cursor

        # Migration from 1.6: merge cog zipcode and tryton zip
        old_table = 'country_zipcode'
        if TableHandler.table_exist(cursor, old_table):
            TableHandler.drop_table(cursor, 'country.zip', 'country_zip')
            cursor.execute('DROP SEQUENCE country_zip_id_seq')
            TableHandler.table_rename(cursor, old_table, cls._table)

        super(Zip, cls).__register__(module_name)

    def get_rec_name(self, name=None):
        return '%s %s' % (self.zip, self.city)

    @classmethod
    def _export_light(cls):
        return set(['country'])

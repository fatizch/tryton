# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import Unique
from trytond.transaction import Transaction
from trytond import backend

from trytond.modules.coog_core import export, model

__all__ = [
    'Zip',
    ]


class Zip(export.ExportImportMixin, model.FunctionalErrorMixIn):
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
        cls._sql_constraints += [
            ('zip_uniq', Unique(t, t.zip, t.city, t.country),
                'This city and this zipcode already exist for this country!'),
            ]

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().connection.cursor()

        # Migration from 1.6: merge cog zipcode and tryton zip
        old_table = 'country_zipcode'
        if TableHandler.table_exist(old_table):
            TableHandler.drop_table('country.zip', 'country_zip')
            cursor.execute('DROP SEQUENCE country_zip_id_seq')
            TableHandler.table_rename(old_table, cls._table)

        super(Zip, cls).__register__(module_name)

    def get_rec_name(self, name):
        return '%s %s' % (self.zip, self.city)

    @classmethod
    def _export_light(cls):
        return set(['country'])

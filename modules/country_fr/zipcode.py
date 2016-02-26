# -*- coding:utf-8 -*-
from trytond.pool import PoolMeta
from trytond.model import Unique
from trytond import backend
from trytond.transaction import Transaction

from trytond.modules.cog_utils import fields

__metaclass__ = PoolMeta
__all__ = [
    'ZipCode',
    ]


class ZipCode:
    __name__ = 'country.zipcode'

    line5 = fields.Char('Line 5', select=True)

    @classmethod
    def __setup__(cls):
        super(ZipCode, cls).__setup__()
        cls._order.insert(3, ('line5', 'ASC'))
        t = cls.__table__()
        cls._sql_constraints = [x for x in cls._sql_constraints if x[0]
            is not 'zip_uniq']
        cls._sql_constraints += [
            ('zip_uniq_all', Unique(t, t.zip, t.city, t.line5, t.country),
                'This city, zipcode, line5 combination already exists'
                ' for this country!'),
            ]
        cls.line5.help = '''AFNOR - Line 5
            Delivery Service
            Identification Thoroughfare Complement BP (P.O box)
            and Locality (if different from the distribution area indicator)'''

    @classmethod
    def __register__(cls, module_name):
        super(ZipCode, cls).__register__(module_name)
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().cursor
        TableHandler(cursor, cls, module_name).drop_constraint(
            'zip_uniq')

    @classmethod
    def default_line5(cls):
        return ''

    def get_rec_name(self, name=None):
        base = super(ZipCode, self).get_rec_name(None)
        if not self.line5:
            return base
        return base + ' ' + self.line5

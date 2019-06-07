# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.modules.coog_core import fields
from trytond.transaction import Transaction

__all__ = [
    'Zip',
    ]


class Zip(metaclass=PoolMeta):
    __name__ = 'country.zip'

    hexa_post_id = fields.Char('Hexa Post Id', select=True)
    insee_code = fields.Char('Insee Code', help='Insee Code', select=True)

    def get_rec_name(self, name):
        if Transaction().context.get('search_with_insee_code', False):
            return '%s %s' % (self.insee_code, self.city)
        else:
            super(Zip, self).get_rec_name(name)

    @classmethod
    def search_rec_name(cls, name, clause):
        if Transaction().context.get('search_with_insee_code', False):
            if clause[1].startswith('!') or clause[1].startswith('not '):
                bool_op = 'AND'
            else:
                bool_op = 'OR'
            return [bool_op,
                ('insee_code',) + tuple(clause[1:]),
                ('city',) + tuple(clause[1:]),
                ]
        else:
            return super(Zip, cls).search_rec_name(name, clause)

# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

from trytond.modules.coog_core import fields

__metaclass__ = PoolMeta
__all__ = [
    'Insurer',
    ]


class Insurer:
    __name__ = 'insurer'

    waiting_account = fields.Many2One('account.account', 'Waiting Account',
        ondelete='RESTRICT')

    @classmethod
    def _export_light(cls):
        return (super(Insurer, cls)._export_light() | set(['waiting_account']))

    def get_func_key(self, name):
        key = super(Insurer, self).get_func_key(name)
        if self.waiting_account:
            key += '|' + self.waiting_account.func_key

    @classmethod
    def search_func_key(cls, name, clause):
        assert clause[1] == '='
        if '|' in clause[2]:
            operands = clause[2].split('|')
            if len(operands) == 2:
                party_code, account_code = clause[2].split('|')
                return [('party.code', clause[1], party_code),
                    ('account.code', clause[1], account_code)]
            else:
                return [('id', '=', None)]
        else:
            return ['OR',
                [('party.code',) + tuple(clause[1:])],
                [('account.code',) + tuple(clause[1:])],
                ]

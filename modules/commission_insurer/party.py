# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

from trytond.modules.coog_core import fields

__metaclass__ = PoolMeta
__all__ = [
    'Insurer',
    ]


class Insurer:
    __metaclass__ = PoolMeta
    __name__ = 'insurer'

    waiting_account = fields.Many2One('account.account', 'Waiting Account',
        ondelete='RESTRICT')

    @classmethod
    def _export_light(cls):
        return (super(Insurer, cls)._export_light() | set(['waiting_account']))

    def get_func_key(self, name):
        key = super(Insurer, self).get_func_key(name)
        if self.waiting_account:
            key += '|' + getattr(self.waiting_account,
                self.waiting_account._func_key)

    @classmethod
    def search_func_key(cls, name, clause):
        assert clause[1] == '='
        if clause[2] is not None and '|' in clause[2]:
            operands = clause[2].split('|')
            if len(operands) == 2:
                party_code, account_code = clause[2].split('|')
                return [('party.code', clause[1], party_code),
                    ('waiting_account.code', clause[1], account_code)]
            else:
                return [('id', '=', None)]
        else:
            return ['OR',
                [('party.code',) + tuple(clause[1:])],
                [('waiting_account.code',) + tuple(clause[1:])],
                ]

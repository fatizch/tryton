import re

from trytond.pool import PoolMeta
from trytond.model import fields

__metaclass__ = PoolMeta
__all__ = [
    'Bank',
    ]


class Bank:
    __name__ = 'bank'
    code_fr = fields.Char('Bank Code', size=5)

    @classmethod
    def __setup__(cls):
        super(Bank, cls).__setup__()
        cls._error_messages.update({
                'wrong_bank_code': 'The bank code %s must contain 5 numeric '
                'chars.',
                })

    def on_change_code_fr(self):
        self.code_fr = self.code_fr.zfill(5)

    @classmethod
    def validate(cls, banks):
        super(Bank, cls).validate(banks)
        for bank in banks:
            if bank.code_fr and not re.match('[0-9]{5}', bank.code_fr):
                cls.raise_user_error('wrong_bank_code', bank.code_fr)

    @classmethod
    def search_rec_name(cls, name, clause):
        return ['OR',
            [('bic',) + tuple(clause[1:])],
            [('party.name',) + tuple(clause[1:])],
            [('party.short_name',) + tuple(clause[1:])],
            [('code_fr',) + tuple(clause[1:])]
            ]

    def get_rec_name(self, name):
        res = super(Bank, self).get_rec_name(name)
        if self.code_fr:
            return '[%s] %s' % (self.code_fr, res)
        return res

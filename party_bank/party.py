#-*- coding:utf-8 -*-
from ibanlib import iban

from trytond.model import fields as fields
from trytond.pool import PoolMeta

from trytond.modules.coop_utils import CoopSQL, utils as utils
from trytond.modules.coop_party import Actor
__metaclass__ = PoolMeta

__all__ = ['Party', 'Bank']


class Party:
    'Party'

    __name__ = 'party.party'
    bank_role = fields.One2Many('party.bank', 'party', 'Bank',
        size=1)
    bank_accounts = fields.One2Many('party.bank_account', 'party',
        'Bank Accounts')

    def get_summary(self, name=None, at_date=None):
        res = super(Party, self).get_summary(name, at_date)
        res += utils.get_field_as_summary(self, 'bank_accounts',
            True, at_date)
        return res


class Bank(CoopSQL, Actor):
    'Bank'

    __name__ = 'party.bank'

    bank_code = fields.Char('Bank Code')
    branch_code = fields.Char('Branch Code')
    bic = fields.Char('BIC', size=11)

    @classmethod
    def __setup__(cls):
        super(Bank, cls).__setup__()
        cls._constraints += [
            ('check_bic', 'invalid_bic'),
            ]
        cls._error_messages.update({
                'invalid_bic': 'Invalid BIC!',
                })

    def check_bic(self):
        return self.bic is None or iban.valid_BIC(self.bic)

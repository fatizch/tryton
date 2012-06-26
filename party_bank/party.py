#-*- coding:utf-8 -*-
from trytond.model import fields as fields
from trytond.pool import PoolMeta

from trytond.modules.coop_utils import CoopSQL
from trytond.modules.insurance_party import Actor
__metaclass__ = PoolMeta

__all__ = ['Party', 'Bank']


class Party:
    'Party'

    __name__ = 'party.party'
    bank_role = fields.One2Many('party.bank', 'party', 'Bank',
        size=1)
    bank_accounts = fields.One2Many('party.bank_account', 'party',
        'Bank Accounts')

    def on_change_is_bank(self):
        return self.on_change_generic('is_bank')


class Bank(CoopSQL, Actor):
    'Bank'

    __name__ = 'party.bank'

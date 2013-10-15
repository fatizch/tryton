#-*- coding:utf-8 -*-
from ibanlib import iban

from trytond.pool import PoolMeta
from trytond.pyson import Not

from trytond.modules.coop_utils import CoopSQL, coop_string, fields, utils
from trytond.modules.coop_party import Actor
from trytond.modules.coop_party.party import STATES_COMPANY

__all__ = [
    'Party',
    'Bank'
]


class Party:
    'Party'

    __name__ = 'party.party'
    __metaclass__ = PoolMeta

    bank_role = fields.One2Many(
        'party.bank', 'party', 'Bank', size=1, states={
            'invisible': Not(STATES_COMPANY),
        })
    bank_accounts = fields.One2Many(
        'party.bank_account', 'party', 'Bank Accounts')
    main_bank_account = fields.Function(
        fields.Many2One('party.bank_account', 'Main Bank Account'),
        'get_main_bank_account_id')

    @classmethod
    def get_summary(cls, parties, name=None, at_date=None, lang=None):
        res = super(Party, cls).get_summary(
            parties, name=name, at_date=at_date, lang=lang)
        for party in parties:
            if party.bank_role:
                res[party.id] += coop_string.get_field_as_summary(
                    party, 'bank_role', True, at_date, lang=lang)
            res[party.id] += coop_string.get_field_as_summary(
                party, 'bank_accounts', True, at_date, lang=lang)
        return res

    def get_bank_accounts(self, at_date=None):
        return utils.get_good_versions_at_date(self, 'bank_accounts', at_date)

    def get_main_bank_account_id(self, name):
        bank_accounts = self.get_bank_accounts(utils.today())
        return bank_accounts[0].id if bank_accounts else None


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

    @classmethod
    def get_summary(cls, parties, name=None, at_date=None, lang=None):
        res = {}
        for party in parties:
            res[party.id] = ''
            res[party.id] += coop_string.get_field_as_summary(
                    party, 'bank_code', True, at_date, lang=lang)
            res[party.id] += coop_string.get_field_as_summary(
                party, 'bic', True, at_date, lang=lang)
        return res

# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import re

from trytond.pyson import Eval
from trytond.pool import PoolMeta, Pool

from trytond.modules.coog_core import fields, model

__all__ = [
    'Bank',
    'Agency',
    'BankAccount',
    ]


class Bank:
    __metaclass__ = PoolMeta
    __name__ = 'bank'

    agencies = fields.One2Many('bank.agency', 'bank', 'Agencies',
        delete_missing=True)

    @classmethod
    def search_rec_name(cls, name, clause):
        return ['OR',
            [('bic',) + tuple(clause[1:])],
            [('party.name',) + tuple(clause[1:])],
            [('agencies.bank_code',) + tuple(clause[1:])]
            ]


class Agency(model.CoogSQL, model.CoogView):
    'Agency'
    __name__ = 'bank.agency'

    bank = fields.Many2One('bank', 'Bank', required=True, ondelete='CASCADE',
        select=True)
    name = fields.Char('Name')
    bank_code = fields.Char('Bank Code', size=5)
    branch_code = fields.Char('Branch Code', size=5)
    address = fields.Many2One('party.address', 'Address', domain=[
            ('party', '=', Eval('bank_party'))], depends=['bank_party'],
        ondelete='RESTRICT')
    bank_party = fields.Function(
        fields.Many2One('party.party', 'Bank Party'),
        'on_change_with_bank_party')

    @classmethod
    def __setup__(cls):
        super(Agency, cls).__setup__()
        cls._error_messages.update({
                'wrong_branch_code': 'The branch code %s must contain 5 '
                'numeric chars.',
                'wrong_bank_code': 'The bank code %s must contain 5 numeric '
                'chars.',
                })

    @classmethod
    def validate(cls, instances):
        super(Agency, cls).validate(instances)
        for agency in instances:
            if agency.bank_code and not re.match('[0-9]{5}', agency.bank_code):
                cls.raise_user_error('wrong_agency_code', agency.bank_code)
            if agency.branch_code and not re.match('[0-9]{5}',
                    agency.branch_code):
                cls.raise_user_error('wrong_branch_code', agency.branch_code)

    @fields.depends('bank_code')
    def on_change_bank_code(self):
        self.bank_code = self.bank_code.zfill(5) if self.bank_code else ''

    @fields.depends('branch_code')
    def on_change_branch_code(self):
        self.branch_code = (self.branch_code or '').zfill(5)

    @fields.depends('bank')
    def on_change_with_bank_party(self, name=None):
        return self.bank.party.id if self.bank else None


class BankAccount:
    __metaclass__ = PoolMeta
    __name__ = 'bank.account'

    @classmethod
    def __setup__(cls):
        super(BankAccount, cls).__setup__()
        cls._error_messages.update({'iban_bank_mismatch':
                'The IBAN and bank do not match'})

    @fields.depends('number', 'numbers', 'bank')
    def on_change_number(self):
        if not self.number:
            return
        self.bank = self.get_bank_from_number()

    def get_bank_identifiers_fr(self, number):
        if (not number or not number.upper().startswith('FR') or
                len(number) < 15):
            return
        return (number[4:9], number[9:14])

    def get_bank_from_number(self):
        pool = Pool()
        Agency = pool.get('bank.agency')
        number = self.number
        if not number:
            return
        number = number.replace(' ', '')
        bank_identifiers_fr = self.get_bank_identifiers_fr(number)
        if not bank_identifiers_fr:
            return
        bank_code, branch_code = bank_identifiers_fr
        agencies = Agency.search([('bank_code', '=', bank_code),
                ('branch_code', '=', branch_code)], limit=1)
        return agencies[0].bank if agencies else None

    def check_iban_matches_bank(self):
        bank_from_iban = self.get_bank_from_number()
        if bank_from_iban and self.bank != bank_from_iban:
            self.raise_user_warning('iban_bank_mismatch', 'iban_bank_mismatch')

    @classmethod
    def validate(cls, accounts):
        super(BankAccount, cls).validate(accounts)
        for account in accounts:
            account.check_iban_matches_bank()

import re
from stdnum.iso7064 import mod_97_10
from stdnum import luhn
from ibanlib import iban

from trytond.model import fields as fields
from trytond.pyson import Eval
from trytond.pool import Pool

from trytond.transaction import Transaction

from trytond.modules.coop_utils import CoopView, CoopSQL

BANK_ACCOUNT_KIND = [('IBAN', 'IBAN'),
                     ('RIB', 'RIB'),
                     ('OT', 'Other'),
                     ('CC', 'Credit Card'),
                    ]


class BankAccount(CoopSQL, CoopView):
    'Bank Account'
    __name__ = 'party.bank_account'

    party = fields.Many2One('party.party', 'Party')
    currency = fields.Many2One('currency.currency', 'Currency',
        states={'required': Eval('kind') != 'CC'})
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    account_numbers = fields.One2Many('party.bank_account_number',
        'bank_account', 'Account Number', required=True)
    agency = fields.Many2One('party.bank', 'Agency')
    address = fields.Many2One('party.address', 'Address',
        domain=[('party', '=', Eval('agency'))],
        depends=['agency'])

    @staticmethod
    def default_currency():
        Currency = Pool().get('currency.currency')
        currencies = Currency.search([('code', '=', 'EUR')], limit=1)
        if len(currencies) > 0:
            return currencies[0].id

    @staticmethod
    def default_account_numbers():
        return [{}]


class BankAccountNumber(CoopSQL, CoopView):
    'Bank account Number'
    __name__ = 'party.bank_account_number'

    bank_account = fields.Many2One('party.bank_account', 'Bank Account')
    kind = fields.Selection(BANK_ACCOUNT_KIND, 'Kind', required=True)
    number = fields.Char('Number', required=True)

    @classmethod
    def __setup__(cls):
        super(BankAccountNumber, cls).__setup__()
        cls._constraints += [
            ('check_number', 'invalid_number'),
            ]
        cls._error_messages.update({
                'invalid_number': 'Invalid number!',
                })

    def check_number(self):
        if self.kind == 'IBAN':
            return self.check_iban()
        elif self.kind == 'RIB':
            return self.check_rib()
        elif self.kind == 'CC':
            return self.check_credit_card()
        return True

    def check_iban(self):
        return iban.valid(self.number)

    def check_rib(self):
        return mod_97_10.is_valid(self.number)

    def check_credit_card(self):
        expr = '^(?:4[0-9]{12}(?:[0-9]{3})?|\
            5[1-5][0-9]{14}|\
            6(?:011|5[0-9][0-9])[0-9]{12}|\
            3[47][0-9]{13}|\
            3(?:0[0-5]|\
            [68][0-9])[0-9]{11}|\
            (?:2131|1800|35\d{3})\d{11})$'
        return re.search(expr, self.number) and luhn.is_valid(self.number)

    @staticmethod
    def default_kind():
        return 'IBAN'

    def calculate_iban_from_rib(self):
        try:
            i = iban. IntAccount(country='FR',
                bank=self.number[1:5],
                branche=self.number[6:11],
                account=self.number[12:23],
                check3=self.number[24:26])
        except iban.IBANError:
            return ''
        else:
            return i.iban

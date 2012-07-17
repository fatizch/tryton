import re
import datetime
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

RIB_LENGTH = 23


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

    @staticmethod
    def default_start_date():
        return datetime.date.today()


class BankAccountNumber(CoopSQL, CoopView):
    'Bank account Number'
    __name__ = 'party.bank_account_number'

    bank_account = fields.Many2One('party.bank_account', 'Bank Account')
    kind = fields.Selection(BANK_ACCOUNT_KIND, 'Kind', required=True)
    number = fields.Char('Number', required=True,
        states={'invisible': Eval('kind') == 'RIB'},
        depends=['kind'],
        on_change_with=['number', 'kind', 'bank_code', 'branch_code',
            'account_number', 'key'])
    bank_code = fields.Function(fields.Char('Bank Code', size=5,
            states={'invisible': Eval('kind') != 'RIB'},
            depends=['kind'],
            on_change=['bank_code']),
        'get_sub_rib', 'set_sub_rib')
    branch_code = fields.Function(fields.Char('Branch Code', size=5,
            states={'invisible': Eval('kind') != 'RIB'},
            depends=['kind'],
            on_change=['branch_code']),
        'get_sub_rib', 'set_sub_rib')
    account_number = fields.Function(fields.Char('Account Number', size=11,
            states={'invisible': Eval('kind') != 'RIB'},
            depends=['kind'],
            on_change=['account_number']),
        'get_sub_rib', 'set_sub_rib')
    key = fields.Function(fields.Char('Key', size=2,
            states={'invisible': Eval('kind') != 'RIB'},
            depends=['kind'],
            on_change=['key']),
        'get_sub_rib', 'set_sub_rib')

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

    @staticmethod
    def get_clean_bank_account(number):
        return number.replace('-', '').replace(' ', '')

    def check_iban(self):
        return self.number != '' and iban.valid(self.number)

    def split_account_number(self):
        if self.kind != 'RIB':
            return self.number
        rib = self.get_clean_bank_account(self.number)
        if len(rib) != RIB_LENGTH:
            return False
        regex = re.compile(r"""^(?P<bank>[0-9]{5})
            (?P<branch>[0-9]{5})
            (?P<account>[0-9A-Z]{11})
            (?P<key>[0-9]{2})$""",
            re.UNICODE | re.IGNORECASE | re.X)
        match = regex.match(rib)
        if not match:
            return False
        return {'bank_code': match.group('bank'),
            'branch_code': match.group('branch'),
            'account_number': match.group('account'),
            'key': match.group('key')}

    def check_rib(self):
        the_dict = self.split_account_number()
        if the_dict == False:
            return False
        account = the_dict['account_number']
        for char in account:
            if char.encode('utf-8').isalpha():
                char = char.upper()
                digit = ord(char) - ord('A') + 1
                digit = (digit > 18 and digit + 1 or digit) % 9
                account = account.replace(char, str(digit))
        calculated_key = 97 - (89 * int(the_dict['bank_code'])
            + 15 * int(the_dict['branch_code'])
            + 3 * int(account)) % 97
        return calculated_key == int(the_dict['key'])

    def check_credit_card(self):
        expr = """^(?:4[0-9]{12}(?:[0-9]{3})?|
            5[1-5][0-9]{14}|
            6(?:011|5[0-9][0-9])[0-9]{12}|3[47][0-9]{13}|
            3(?:0[0-5]|[68][0-9])[0-9]{11}|
            (?:2131|1800|35\d{3})\d{11})$"""
        return (re.search(expr, self.number, re.X)
            and luhn.is_valid(self.number))

    @staticmethod
    def default_kind():
        return 'RIB'

    def calculate_iban_from_rib(self):
        try:
            the_dict = self.split_account_number()
            if not the_dict:
                return ''
            i = iban. IntAccount(country='FR',
                bank=the_dict['bank_code'],
                branche=the_dict['branch_code'],
                account=the_dict['account_number'],
                check3=the_dict['key'])
        except iban.IBANError:
            return ''
        else:
            return i.iban

    def get_sub_rib(self, name):
        if self.kind == 'RIB':
            the_dict = self.split_account_number()
            if self.number and the_dict:
                return the_dict[name]
        return ''

    @classmethod
    def set_sub_rib(cls, bank_account_nbs, name, value):
        for nb in bank_account_nbs:
            if not nb.number or len(nb.number) < RIB_LENGTH:
                nb.number = '0' * RIB_LENGTH
            if name == 'bank_code':
                nb.number = value + nb.number[5:RIB_LENGTH]
            elif name == 'branch_code':
                nb.number = nb.number[0:5] + value + nb.number[10:RIB_LENGTH]
            elif name == 'account_number':
                nb.number = nb.number[0:10] + value + nb.number[21:RIB_LENGTH]
            elif name == 'key':
                nb.number = nb.number[0:21] + value
            cls.write([nb], {'number': nb.number})

    def on_change_with_number(self, name):
        if self.kind != 'RIB':
            return self.number
        res = getattr(self, 'bank_code', '0').rjust(5, '0')
        res += getattr(self, 'branch_code', '0').rjust(5, '0')
        res += getattr(self, 'account_number', '0').rjust(11, '0')
        res += getattr(self, 'key', '0').rjust(2, '0')
        return res

    def on_change_sub_rib(self, name):
        res = {}
        field = getattr(self.__class__, name)
        if field and hasattr(field, 'size'):
            res[name] = getattr(self, name).rjust(field.size, '0')
            return res
        return res

    def on_change_bank_code(self):
        return self.on_change_sub_rib('bank_code')

    def on_change_branch_code(self):
        return self.on_change_sub_rib('branch_code')

    def on_change_account_number(self):
        return self.on_change_sub_rib('account_number')

    def on_change_key(self):
        return self.on_change_sub_rib('key')

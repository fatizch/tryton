import copy
import re
from ibanlib import iban

from trytond.model import ModelView, fields
from trytond.pyson import Eval
from trytond.pool import PoolMeta


RIB_LENGTH = 23


__all__ = [
    'BankAccountNumber',
    ]


class BankAccountNumber():
    'Bank account Number'

    __name__ = 'bank.account_number'
    __metaclass__ = PoolMeta

    bank_code = fields.Function(fields.Char('Bank Code', size=5,
            states={'invisible': Eval('kind') != 'RIB'},),
        'get_sub_rib')
    branch_code = fields.Function(fields.Char('Branch Code', size=5,
            states={'invisible': Eval('kind') != 'RIB'},),
        'get_sub_rib')
    account_number = fields.Function(fields.Char('Account Number', size=11,
            states={'invisible': Eval('kind') != 'RIB'},),
        'get_sub_rib')
    key = fields.Function(fields.Char('Key', size=2,
            states={'invisible': Eval('kind') != 'RIB'},),
        'get_sub_rib')

    @classmethod
    def __setup__(cls):
        super(BankAccountNumber, cls).__setup__()
        cls.kind = copy.copy(cls.kind)
        cls.kind.selection.append(('RIB', 'RIB'))
        cls.kind = list(set(cls.kind))

        cls._buttons.update({
                'button_migrate_rib_to_iban': {
                    'invisible': Eval('kind') != 'RIB',
                    },
                })

    def is_number_valid(self):
        res = super(BankAccountNumber, self).is_number_valid()
        if res and self.kind == 'RIB':
            return self.check_rib(self.number)
        return res

    @staticmethod
    def get_clean_bank_account(number):
        return number.replace('-', '').replace(' ', '')

    @staticmethod
    def split_rib(number):
        rib = BankAccountNumber.get_clean_bank_account(number)
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

    def split_account_number(self):
        if self.kind != 'RIB':
            return self.number
        return self.split_rib(self.number)

    @staticmethod
    def calculate_key_rib(bank_code, branch_code, nb):
        for char in str(nb):
            if char.encode('utf-8').isalpha():
                char = char.upper()
                digit = ord(char) - ord('A') + 1
                digit = (digit > 18 and digit + 1 or digit) % 9
                nb = nb.replace(char, str(digit))
        key = str(97 - (89 * int(bank_code) + 15 * int(branch_code)
                + 3 * int(nb)) % 97).zfill(2)
        return key

    @staticmethod
    def check_rib(number):
        the_dict = BankAccountNumber.split_rib(number)
        if not the_dict:
            return False
        return (BankAccountNumber.calculate_key_rib(
            the_dict['bank_code'], the_dict['branch_code'],
            the_dict['account_number']) == the_dict['key'])

    @staticmethod
    def calculate_iban_from_rib(number):
        try:
            the_dict = BankAccountNumber.split_rib(number)
            if not the_dict:
                return ''
            i = iban.IntAccount(country='FR',
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

    def get_rec_name(self, name):
        if self.kind == 'RIB':
            return '%s %s %s %s' % (self.bank_code, self.branch_code,
                self.account_number, self.key)
        else:
            return self.number

    @classmethod
    @ModelView.button
    def button_migrate_rib_to_iban(cls, numbers):
        for number in numbers:
            if number.kind == 'RIB':
                iban = BankAccountNumber.calculate_iban_from_rib(number.number)
                if iban:
                    number.kind = 'IBAN'
                    number.number = iban
                    number.save()

import re
from ibanlib import iban

from trytond.pool import PoolMeta
from trytond.model import fields, ModelView
from trytond.pyson import Eval

__metaclass__ = PoolMeta

__all__ = [
    'Bank',
    'BankAccountNumber',
    ]

RIB_LENGTH = 23


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
        return {'code_fr': self.code_fr.zfill(5)}

    @classmethod
    def validate(cls, banks):
        super(Bank, cls).validate(banks)
        for bank in banks:
            if not re.match('[0-9]{5}', bank.code_fr):
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


class BankAccountNumber:
    __name__ = 'bank.account.number'

    bank_code = fields.Function(fields.Char('Bank Code', size=5,
            states={'invisible': Eval('type') != 'rib'}, depends=['type']),
        'get_sub_rib')
    branch_code = fields.Function(fields.Char('Branch Code', size=5,
            states={'invisible': Eval('type') != 'rib'}, depends=['type']),
        'get_sub_rib')
    account_number = fields.Function(fields.Char('Account Number', size=11,
            states={'invisible': Eval('type') != 'rib'}, depends=['type']),
        'get_sub_rib')
    key = fields.Function(fields.Char('Key', size=2,
            states={'invisible': Eval('type') != 'rib'}, depends=['type']),
        'get_sub_rib')

    @classmethod
    def __setup__(cls):
        super(BankAccountNumber, cls).__setup__()
        cls.type.selection.append(('rib', 'RIB'))
        cls.type.selection = list(set(cls.type.selection))

        cls._error_messages.update({
                'invalid_rib_number': ('Invalid RIB number : %s')})

        cls._buttons.update({
                'button_migrate_rib_to_iban': {
                    'invisible': Eval('type') != 'rib',
                    },
                })

    @classmethod
    def validate(cls, numbers):
        super(BankAccountNumber, cls).validate(numbers)
        for number in numbers:
            cls.check_rib(number)

    def check_rib(self):
        res = True
        if not hasattr(self, 'type'):
            return res
        if self.type == 'rib':
            res = self.check_rib_number(self.number)
        if not res:
            self.raise_user_error('invalid_rib_number', (self.number))
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
        if self.type != 'rib':
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
    def check_rib_number(number):
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
        if self.type == 'rib':
            the_dict = self.split_account_number()
            if self.number and the_dict:
                return the_dict[name]
        return ''

    @fields.depends('bank_code')
    def on_change_bank_code(self):
        return {'number': self.bank_code, 'branch_code': '',
            'account_number': '', 'key': ''}

    @fields.depends('branch_code', 'bank_code')
    def on_change_branch_code(self):
        return {'number': self.bank_code + self.branch_code,
            'account_number': '', 'key': ''}

    @fields.depends('account_number', 'branch_code', 'bank_code')
    def on_change_account_number(self):
        return {'number': self.bank_code + self.branch_code +
            self.account_number, 'key': ''}

    @fields.depends('key', 'bank_code', 'branch_code', 'account_number')
    def on_change_key(self):
        return {'number': self.bank_code + self.branch_code +
            self.account_number + self.key}

    def pre_validate(self):
        super(BankAccountNumber, self).pre_validate()
        self.check_rib()

    def get_rec_name(self, name):
        if self.type == 'rib':
            return '%s %s %s %s' % (self.bank_code, self.branch_code,
                self.account_number, self.key)
        else:
            return self.number

    @classmethod
    def get_summary(cls, numbers, name=None, at_date=None, lang=None):
        return dict([(nb.id, '%s : %s' % (nb.type, nb.rec_name))
            for nb in numbers])

    @classmethod
    @ModelView.button
    def button_migrate_rib_to_iban(cls, numbers):
        for number in numbers:
            if number.type == 'rib':
                iban = BankAccountNumber.calculate_iban_from_rib(number.number)
                if iban:
                    number.type = 'iban'
                    number.number = iban
                    number.save()

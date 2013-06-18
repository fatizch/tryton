import re
# from stdnum import luhn
from ibanlib import iban

from trytond.pyson import Eval
from trytond.pool import Pool
from trytond.transaction import Transaction

from trytond.modules.coop_utils import CoopView, CoopSQL, utils, fields
from trytond.modules.coop_utils import coop_string

BANK_ACCOUNT_KIND = [
    ('IBAN', 'IBAN'),
    ('RIB', 'RIB'),
    ('OT', 'Other'),
]

RIB_LENGTH = 23


class BankAccount(CoopSQL, CoopView):
    'Bank Account'
    __name__ = 'party.bank_account'

    party = fields.Many2One('party.party', 'Party',
        ondelete='CASCADE')
    currency = fields.Many2One('currency.currency', 'Currency',
        states={'required': Eval('kind') != 'CC'})
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    account_numbers = fields.One2Many('party.bank_account_number',
        'bank_account', 'Account Number', required=False)
    agency = fields.Many2One('party.party', 'Agency',
        domain=[('is_bank', '=', True)])
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
        if not Transaction().context.get('__importing__'):
            return [{}]
        else:
            return []

    @staticmethod
    def default_start_date():
        return utils.today()

    @classmethod
    def get_summary(cls, bank_accounts, name=None, at_date=None, lang=None):
        res = {}
        for bank_acc in bank_accounts:
            res[bank_acc.id] = coop_string.get_field_as_summary(bank_acc,
                'account_numbers', False, at_date, lang=lang)
        return res

    @classmethod
    def default_party(cls):
        for_party = Transaction().context.get('for_party', None)
        if not for_party:
            return
        return for_party

    def get_rec_name(self, name=None):
        res = ''
        if self.agency:
            res += self.agency.rec_name
        if self.account_numbers:
            if res:
                res += ' '
            res += '[%s]' % self.account_numbers[0].rec_name
        return res


class BankAccountNumber(CoopSQL, CoopView):
    'Bank account Number'
    __name__ = 'party.bank_account_number'

    bank_account = fields.Many2One('party.bank_account', 'Bank Account',
        ondelete='CASCADE')
    kind = fields.Selection(BANK_ACCOUNT_KIND, 'Kind', required=True)
    number = fields.Char('Number', required=True)
    bank_code = fields.Function(fields.Char('Bank Code', size=5,
            states={'invisible': Eval('kind') != 'RIB'},
            depends=['kind'],
            on_change=['bank_code']),
        'get_sub_rib')
    branch_code = fields.Function(fields.Char('Branch Code', size=5,
            states={'invisible': Eval('kind') != 'RIB'},
            depends=['kind'],
            on_change=['branch_code']),
        'get_sub_rib')
    account_number = fields.Function(fields.Char('Account Number', size=11,
            states={'invisible': Eval('kind') != 'RIB'},
            depends=['kind'],
            on_change=['account_number']),
        'get_sub_rib')
    key = fields.Function(fields.Char('Key', size=2,
            states={'invisible': Eval('kind') != 'RIB'},
            depends=['kind'],
            on_change=['key']),
        'get_sub_rib')

    @classmethod
    def __setup__(cls):
        super(BankAccountNumber, cls).__setup__()
        cls._error_messages.update({
            'invalid_number': ('Invalid %s number : %s')})
        cls._buttons.update({
                'button_migrate_rib_to_iban': {
                    'invisible': Eval('kind') != 'RIB',
                    },
                })

    @classmethod
    def validate(cls, numbers):
        super(BankAccountNumber, cls).validate(numbers)
        for number in numbers:
            cls.check_number(number)

    def check_number(self):
        res = True
        if not hasattr(self, 'kind'):
            return res
        if self.kind == 'IBAN':
            res = self.check_iban()
        elif self.kind == 'RIB':
            res = self.check_rib(self.number)
        if not res:
            self.raise_user_error('invalid_number', (self.kind, self.number))
        return res

    @staticmethod
    def get_clean_bank_account(number):
        return number.replace('-', '').replace(' ', '')

    def check_iban(self):
        return self.number != '' and iban.valid(self.number)

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
    def default_kind():
        return 'IBAN'

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

    @classmethod
    def set_sub_rib(cls, bank_account_nbs, name, value):
        pass
        # for nb in bank_account_nbs:
        #     print nb.kind, nb.number
        #     if nb.kind != 'RIB':
        #         continue
        #     if not nb.number or len(nb.number) < RIB_LENGTH:
        #         nb.number = '0' * RIB_LENGTH
        #     if name == 'bank_code':
        #         nb.number = value + nb.number[5:RIB_LENGTH]
        #     elif name == 'branch_code':
        #         nb.number = nb.number[0:5] + value + nb.number[10:RIB_LENGTH]
        #     elif name == 'account_number':
        #         nb.number = nb.number[0:10] + value + nb.number[21:RIB_LENGTH]
        #     elif name == 'key':
        #         nb.number = nb.number[0:21] + value
        #     cls.write([nb], {'number': nb.number})

    def on_change_with_number(self, name=None):
        pass
        # if self.kind != 'RIB':
        #     return self.number
        # res = coop_string.zfill(self, 'bank_code',)
        # res += coop_string.zfill(self, 'branch_code')
        # res += coop_string.zfill(self, 'account_number')
        # res += coop_string.zfill(self, 'key')
        # return res

    def on_change_sub_rib(self, name):
        return getattr(self, name)
        res = {}
        val = coop_string.zfill(self, name)
        if val:
            res[name] = val
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

    def pre_validate(self):
        self.check_number()

    def get_rec_name(self, name):
        if self.kind == 'RIB':
            return '%s %s %s %s' % (self.bank_code, self.branch_code,
                self.account_number, self.key)
        else:
            return self.number

    @classmethod
    def get_summary(cls, numbers, name=None, at_date=None, lang=None):
        return dict([(nb.id, '%s : %s' % (nb.kind, nb.rec_name))
            for nb in numbers])

    @classmethod
    @CoopView.button
    def button_migrate_rib_to_iban(cls, numbers):
        for number in numbers:
            if number.kind == 'RIB':
                iban = BankAccountNumber.calculate_iban_from_rib(number.number)
                if iban:
                    number.kind = 'IBAN'
                    number.number = iban
                    number.save()

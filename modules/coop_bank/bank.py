from ibanlib import iban

from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction

from trytond.modules.coop_utils import utils, fields
from trytond.modules.coop_utils import coop_string


__metaclass__ = PoolMeta

__all__ = [
    'Bank',
    'BankAccount',
    'BankAccountNumber',
    ]


class Bank():
    'Bank'

    __name__ = 'bank'

    @classmethod
    def __setup__(cls):
        super(Bank, cls).__setup__()
        cls._error_messages.update({
                'invalid_bic': ('Invalid BIC : %s'),
                })

    @classmethod
    def validate(cls, banks):
        super(Bank, cls).validate(banks)
        for bank in banks:
            cls.check_bic(bank)

    def Bank(self):
        super(Bank, self).pre_validate()
        self.check_bic()

    def check_bic(self):
        if self.bic and not iban.valid_BIC(self.bic):
            self.raise_user_error('invalid_bic', (self.bic))

    @classmethod
    def get_summary(cls, parties, name=None, at_date=None, lang=None):
        res = {}
        for party in parties:
            res[party.id] = ''
            res[party.id] += coop_string.get_field_as_summary(
                party, 'bic', True, at_date, lang=lang)
        return res

    @classmethod
    def get_var_names_for_light_extract(cls):
        return ['bic']


class BankAccount():
    'Bank Account'

    __name__ = 'bank.account'

    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    numbers_as_char = fields.Function(
        fields.Char('Numbers'),
        'get_numbers_as_char')
    number = fields.Function(
        fields.Char('Main Account Number'),
        'get_main_bank_account_number')

    @staticmethod
    def default_currency():
        Currency = Pool().get('currency.currency')
        currencies = Currency.search([('code', '=', 'EUR')], limit=1)
        if len(currencies) > 0:
            return currencies[0].id

    @staticmethod
    def default_numbers():
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
                'numbers', False, at_date, lang=lang)
        return res

    def get_numbers_as_char(self, name):
        return ', '.join([x.rec_name for x in self.numbers])

    @classmethod
    def get_var_names_for_light_extract(cls):
        return ['number']

    @classmethod
    def get_var_names_for_full_extract(cls):
        return ['numbers', ('bank', 'light'), ('currency', 'light')]

    def get_main_bank_account_number(self, name):
        ibans = [x.number for x in self.numbers if x.kind == 'iban']
        if ibans:
            return ibans[-1].number
        elif self.numbers:
            return self.numbers[-1].number


class BankAccountNumber():
    'Bank account Number'

    __name__ = 'bank.account.number'

    @classmethod
    def __setup__(cls):
        super(BankAccountNumber, cls).__setup__()
        cls._error_messages.update({
                'invalid_number': ('Invalid %s number : %s')})

    @classmethod
    def validate(cls, numbers):
        super(BankAccountNumber, cls).validate(numbers)
        for number in numbers:
            cls.check_number(number)

    def check_number(self):
        res = True
        if not hasattr(self, 'type'):
            return
        if self.type == 'iban':
            res = self.check_iban()
        if not res:
            self.raise_user_error('invalid_number', (self.type, self.number))

    def check_iban(self):
        return self.number != '' and iban.valid(self.number)

    @staticmethod
    def default_type():
        return 'iban'

    def pre_validate(self):
        super(BankAccountNumber, self).pre_validate()
        self.check_number()

    @classmethod
    def get_summary(cls, numbers, name=None, at_date=None, lang=None):
        return dict([(nb.id, '%s : %s' % (nb.type, nb.rec_name))
            for nb in numbers])

    @classmethod
    def get_var_names_for_full_extract(cls):
        return ['kind', 'number', ]

    @classmethod
    def get_var_names_for_light_extract(cls):
        return ['number']

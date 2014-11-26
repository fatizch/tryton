from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from trytond.model import fields as tryton_fields
from trytond.pyson import If, Bool, Eval

from trytond.modules.cog_utils import utils, fields, export
from trytond.modules.cog_utils import coop_string


__metaclass__ = PoolMeta

__all__ = [
    'Bank',
    'BankAccount',
    'BankAccountNumber',
    'BankAccountParty',
    ]


class Bank(export.ExportImportMixin):
    __name__ = 'bank'
    _func_key = 'bic'

    main_address = fields.Function(
        fields.Many2One('party.address', 'Main Address'),
        'get_main_address_id')

    @classmethod
    def __setup__(cls):
        super(Bank, cls).__setup__()
        cls._sql_constraints += [
            ('bic_uniq', 'UNIQUE(bic)', 'The bic must be unique!'),
            ]
        cls._error_messages.update({
                'invalid_bic': ('Invalid BIC : %s'),
                })

    @classmethod
    def _export_keys(cls):
        return set(['bic'])

    @classmethod
    def validate(cls, banks):
        super(Bank, cls).validate(banks)
        for bank in banks:
            cls.check_bic(bank)

    def pre_validate(self):
        super(Bank, self).pre_validate()
        self.check_bic()

    def check_bic(self):
        if self.bic and not self.valid_BIC(self.bic):
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

    def get_rec_name(self, name):
        res = '[%s] %s' % (self.bic, self.party.name if self.party else '')
        return res

    @classmethod
    def search_rec_name(cls, name, clause):
        return ['OR',
            [('bic',) + tuple(clause[1:])],
            [('party.name',) + tuple(clause[1:])],
            [('party.short_name',) + tuple(clause[1:])],
            ]

    def get_main_address_id(self, name):
        return (self.party.main_address.id
            if self.party and self.party.main_address else None)

    @classmethod
    def valid_BIC(cls, bic):
        """Check validity of BIC"""
        bic = bic.strip()
        if len(bic) != 8 and len(bic) != 11:
            return False
        if not bic[:6].isalpha():
            return False
        if not bic[6:8].isalnum():
            return False
        return True


class BankAccount(export.ExportImportMixin):
    __name__ = 'bank.account'
    _func_key = 'func_key'

    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    number = fields.Function(
        fields.Char('Main Account Number'),
        'get_main_bank_account_number',
        searcher='search_main_bank_account_number')
    func_key = fields.Function(fields.Char('Functional Key'),
        'get_func_key', searcher='search_func_key')

    @classmethod
    def _export_light(cls):
        return (super(BankAccount, cls)._export_light() |
            set(['bank', 'currency']))

    @classmethod
    def _export_skips(cls):
        return (super(BankAccount, cls)._export_skips() |
            set(['owners']))

    @classmethod
    def __setup__(cls):
        super(BankAccount, cls).__setup__()
        cls.numbers.required = False
        cls.numbers.states['required'] = If(
            Bool(Eval('context', {}).get('__importing__', '')),
            False, True)

    @classmethod
    def _export_keys(cls):
        return set(['number'])

    @classmethod
    def search_main_bank_account_number(cls, name, clause):
        pool = Pool()
        account = pool.get('bank.account').__table__()
        number = pool.get('bank.account.number').__table__()
        _, operator, value = clause
        Operator = tryton_fields.SQL_OPERATORS[operator]
        query_table = account.join(number, condition=(
                account.id == number.account))
        query = query_table.select(account.id, where=Operator(
                number.number, getattr(cls, name).sql_format(value)))
        return [('id', 'in', query)]

    @staticmethod
    def default_currency():
        Currency = Pool().get('currency.currency')
        currencies = Currency.search([('code', '=', 'EUR')], limit=1)
        if len(currencies) > 0:
            return currencies[0].id

    @staticmethod
    def default_numbers():
        if not Transaction().context.get('__importing__'):
            return [{'sequence': 0}]
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
        ibans = [x for x in self.numbers if x.type == 'iban']
        if ibans:
            return ibans[-1].number
        elif self.numbers:
            return self.numbers[-1].number

    def get_synthesis_rec_name(self, name):
        return '%s : %s' % (self.numbers[0].type,
            self.numbers[0].number)

    def get_func_key(self, name):
        return self.numbers[0].number_compact

    @classmethod
    def search_func_key(cls, name, clause):
        return [('numbers',) + tuple(clause[1:])]

    @classmethod
    def add_func_key(cls, values):
        values['_func_key'] = values['numbers'][0]['number']


class BankAccountNumber(export.ExportImportMixin):
    __name__ = 'bank.account.number'
    _func_key = 'number_compact'

    @classmethod
    def __setup__(cls):
        super(BankAccountNumber, cls).__setup__()
        cls._sql_constraints += [
            ('number_uniq', 'UNIQUE(number)', 'The number must be unique!'),
            ]

    @staticmethod
    def default_type():
        return 'iban'

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

    @classmethod
    def search_rec_name(cls, name, clause):
        return ['OR',
            [('number',) + tuple(clause[1:])],
            [('number_compact',) + tuple(clause[1:])],
            ]

    @classmethod
    def add_func_key(cls, values):
        values['_func_key'] = values['number']


class BankAccountParty:
    'Bank Account - Party'
    __name__ = 'bank.account-party.party'

    def get_synthesis_rec_name(self, name):
        if self.account:
            return self.account.get_synthesis_rec_name(name)

    def get_icon(self, name=None):
        return 'coopengo-bank_account'

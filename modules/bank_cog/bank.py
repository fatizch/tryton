# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool, PoolMeta
from trytond.model import fields as tryton_fields, Unique
from trytond.pyson import Eval

from trytond.modules.coog_core import utils, fields, export
from trytond.modules.coog_core import coog_string


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

    name = fields.Char('Name')
    address = fields.Many2One('party.address', 'Address',
        domain=[('party', '=', Eval('party'))], depends=['party'],
        ondelete='RESTRICT')

    @classmethod
    def __setup__(cls):
        super(Bank, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('bic_uniq', Unique(t, t.bic), 'The bic must be unique!'),
            ]
        cls._error_messages.update({
                'invalid_bic': ('Invalid BIC : %s'),
                })
        cls.bic.select = True

    @classmethod
    def create(cls, vlist):
        vlist = [x.copy() for x in vlist]
        for vals in vlist:
            if vals.get('bic', None) and len(vals['bic']) == 8:
                vals['bic'] += 'XXX'
        return super(Bank, cls).create(vlist)

    @classmethod
    def validate(cls, banks):
        super(Bank, cls).validate(banks)
        for bank in banks:
            cls.check_bic(bank)

    @fields.depends('bic')
    def pre_validate(self):
        super(Bank, self).pre_validate()
        self.check_bic()

    def check_bic(self):
        if self.bic and not self.valid_BIC(self.bic):
            self.raise_user_error('invalid_bic', (self.bic))

    def get_rec_name(self, name):
        res = '[%s] %s' % (self.bic, self.party.name if self.party else '')
        return res

    @classmethod
    def search_rec_name(cls, name, clause):
        return ['OR',
            [('bic',) + tuple(clause[1:])],
            [('party.name',) + tuple(clause[1:])],
            [('party.commercial_name',) + tuple(clause[1:])],
            ]

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

    @fields.depends('bic')
    def on_change_with_bic(self):
        return self.bic.upper().strip() if self.bic else ''


class BankAccount(export.ExportImportMixin):
    __name__ = 'bank.account'
    _func_key = 'func_key'

    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    number = fields.Function(
        fields.Char('Number', required=True),
        'get_main_bank_account_number', 'setter_void',
        searcher='search_main_bank_account_number')
    owners_name = fields.Function(
        fields.Char('Owners'), 'on_change_with_owners_name',
        searcher='search_owners_name')
    func_key = fields.Function(fields.Char('Functional Key'),
        'get_func_key', searcher='search_func_key')
    icon = fields.Function(fields.Char('Icon'), 'get_icon')

    @classmethod
    def _export_light(cls):
        return (super(BankAccount, cls)._export_light() |
            set(['bank', 'currency']))

    @classmethod
    def _export_skips(cls):
        return (super(BankAccount, cls)._export_skips() |
            set(['owners']))

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
    def default_start_date():
        return utils.today()

    def get_summary_content(self, label, at_date=None, lang=None):
        return coog_string.get_field_summary(self, 'numbers', True, at_date,
            lang)

    def get_numbers_as_char(self, name):
        return ', '.join([x.rec_name for x in self.numbers])

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

    def get_icon(self, name):
        return 'coopengo-bank_account'

    @classmethod
    def search_func_key(cls, name, clause):
        return [('numbers',) + tuple(clause[1:])]

    @classmethod
    def search_owners_name(cls, name, clause):
        return [('owners',) + tuple(clause[1:])]

    @classmethod
    def add_func_key(cls, values):
        values['_func_key'] = values['numbers'][0]['number']

    @fields.depends('number', 'numbers')
    def on_change_with_numbers(self):
        if not self.numbers:
            return {'add': [(-1, {'number': self.number, 'type': 'iban'})]}
        else:
            return {'update': [
                    {'id': self.numbers[0].id, 'number': self.number},
                    ]}

    @fields.depends('owners')
    def on_change_with_owners_name(self, name=None):
        return ','.join([x.rec_name for x in self.owners])

    @classmethod
    def setter_void(cls, objects, name, values):
        pass

    @fields.depends('numbers')
    def pre_validate(self):
        super(BankAccount, self).pre_validate()
        for number in self.numbers:
            number.pre_validate()

    def objects_using_me_for_party(self, for_party=None):
        for n in self.numbers:
            objects = n.objects_using_me_for_party(for_party)
            if objects:
                return objects


class BankAccountNumber(export.ExportImportMixin):
    __name__ = 'bank.account.number'
    _func_key = 'number_compact'

    @classmethod
    def __setup__(cls):
        super(BankAccountNumber, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('number_uniq', Unique(t, t.number), 'The number must be unique!'),
            ]

    @staticmethod
    def default_type():
        return 'iban'

    def get_summary_content(self, label, at_date=None, lang=None):
        return (self.type, self.rec_name)

    @classmethod
    def search_rec_name(cls, name, clause):
        return ['OR',
            [('number',) + tuple(clause[1:])],
            [('number_compact',) + tuple(clause[1:])],
            ]

    @classmethod
    def add_func_key(cls, values):
        values['_func_key'] = values['number']

    def objects_using_me_for_party(self, for_party=None):
        return None


class BankAccountParty:
    'Bank Account - Party'
    __name__ = 'bank.account-party.party'

    @classmethod
    def __setup__(cls):
        super(BankAccountParty, cls).__setup__()
        cls._error_messages.update({
                'bank_account_used': ('Bank account "%(bank_account)s" is '
                    'used on "%(object)s"'),
                })

    def get_synthesis_rec_name(self, name):
        if self.account:
            return self.account.get_synthesis_rec_name(name)

    def get_icon(self, name=None):
        return 'coopengo-bank_account'

    @classmethod
    def delete(cls, records):
        for r in records:
            objects = r.account.objects_using_me_for_party(r.owner)
            if objects:
                cls.raise_user_error('bank_account_used', {
                    'bank_account': r.account.rec_name,
                    'object': ', '.join(['%s %s' % (
                                o.__class__.__name__,
                                o.rec_name)
                            for o in objects]), })
        super(BankAccountParty, cls).delete(records)

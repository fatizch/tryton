from ibanlib import iban

from trytond.model import ModelView, ModelSQL, fields
from trytond.pool import Pool

__all__ = [
    'BankAccount',
    'BankAccountNumber',
    ]


class BankAccount(ModelSQL, ModelView):
    'Bank Account'

    __name__ = 'bank.account'

    party = fields.Many2One('party.party', 'Party', ondelete='CASCADE')
    currency = fields.Many2One('currency.currency', 'Currency', required=True)
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    account_numbers = fields.One2Many('bank.account_number',
        'bank_account', 'Account Number', required=False)
    bank = fields.Many2One('bank.bank', 'Bank')

    @staticmethod
    def default_start_date():
        return Pool().get('ir.date').today()

    def get_rec_name(self, name=None):
        res = ''
        if self.bank:
            res += self.bank.rec_name
        if self.account_numbers:
            if res:
                res += ' '
            res += '%s [%s]' % (
                self.account_numbers[0].kind,
                self.account_numbers[0].rec_name)
        return res


class BankAccountNumber(ModelSQL, ModelView):
    'Bank account Number'

    __name__ = 'bank.account_number'
    _rec_name = 'number'

    bank_account = fields.Many2One('bank.account', 'Bank Account',
        ondelete='CASCADE')
    kind = fields.Selection([('IBAN', 'IBAN'), ('OTHER', 'Other')], 'Kind',
        required=True)
    number = fields.Char('Number', required=True)

    @classmethod
    def __setup__(cls):
        super(BankAccountNumber, cls).__setup__()
        cls._error_messages.update({
                'invalid_number': ('Invalid %s number: %s')})

    @classmethod
    def validate(cls, numbers):
        super(BankAccountNumber, cls).validate(numbers)
        for number in numbers:
            cls.check_number(number)

    def is_number_valid(self):
        if not hasattr(self, 'kind'):
            return True
        if self.kind == 'IBAN':
            return self.check_iban()
        return True

    def check_number(self):
        if not self.is_number_valid():
            self.raise_user_error('invalid_number', (self.kind, self.number))

    def check_iban(self):
        return self.number != '' and iban.valid(self.number)

    @staticmethod
    def default_kind():
        return 'IBAN'

    def pre_validate(self):
        self.check_number()

from trytond.model import ModelView, ModelSQL, fields
from trytond.pyson import Eval

__all__ = [
    'OldBank',
    'OldBankAccount',
    'OldBankAccountNumber',
    ]


class OldBank(ModelView, ModelSQL):
    'Bank'

    __name__ = 'party.bank'

    party = fields.Many2One('party.party', 'Party')
    bank_code = fields.Char('Bank Code')
    branch_code = fields.Char('Branch Code')
    bic = fields.Char('BIC', size=11)


class OldBankAccount(ModelView, ModelSQL):
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
    agency = fields.Many2One('party.party', 'Agency')
    address = fields.Many2One('party.address', 'Address',
        domain=[('party', '=', Eval('agency'))],
        depends=['agency'])
    numbers_as_char = fields.Function(
        fields.Char('Numbers'),
        'get_numbers_as_char')
    bank = fields.Many2One('party.bank', 'Bank')


class OldBankAccountNumber(ModelView, ModelSQL):
    'Bank account Number'
    __name__ = 'party.bank_account_number'

    bank_account = fields.Many2One('party.bank_account', 'Bank Account',
        ondelete='CASCADE')
    kind = fields.Char('Kind', required=True)
    number = fields.Char('Number', required=True)

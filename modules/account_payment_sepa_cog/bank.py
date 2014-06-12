from trytond.pyson import Eval
from trytond.model import ModelSQL, ModelView
from trytond.modules.cog_utils import fields

__all__ = [
    'BankAccountNumber',
    ]


class BankAccountNumber(ModelSQL, ModelView):
    'Bank Account Number'
    __name__ = 'bank.account.number'

    mandates = fields.One2Many('account.payment.sepa.mandate',
        'account_number', 'Sepa Mandates', states={
            'invisible': Eval('type') != 'iban',
            'readonly': True},
        domain=[('party.bank_accounts', '=', Eval('account'))],
        depends=['account'])

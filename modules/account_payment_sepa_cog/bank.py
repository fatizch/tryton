from trytond.pyson import Eval
from trytond.model import ModelSQL, ModelView
from trytond.pool import PoolMeta

from trytond.modules.cog_utils import fields

__metaclass__ = PoolMeta
__all__ = [
    'Bank',
    'BankAccountNumber',
    ]


class Bank:
    __name__ = 'bank'

    @classmethod
    def __setup__(cls):
        super(Bank, cls).__setup__()
        cls.bic.required = True


class BankAccountNumber(ModelSQL, ModelView):
    'Bank Account Number'
    __name__ = 'bank.account.number'

    mandates = fields.One2Many('account.payment.sepa.mandate',
        'account_number', 'Sepa Mandates', states={
            'invisible': Eval('type') != 'iban',
            'readonly': True},
        domain=[('party.bank_accounts', '=', Eval('account'))],
        depends=['account'])

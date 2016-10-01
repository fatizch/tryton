# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pyson import Eval
from trytond.pool import PoolMeta, Pool

from trytond.modules.coog_core import fields

__metaclass__ = PoolMeta
__all__ = [
    'Bank',
    'BankAccount',
    'BankAccountNumber',
    ]


class Bank:
    __name__ = 'bank'

    @classmethod
    def __setup__(cls):
        super(Bank, cls).__setup__()
        cls.bic.required = True


class BankAccount:
    __name__ = 'bank.account'

    def objects_using_me_for_party(self, party=None):
        objects = super(BankAccount, self).objects_using_me_for_party(party)
        if objects:
            return objects
        Payment = Pool().get('account.payment')
        domain = [('bank_account', '=', self)]
        if party:
            domain.append(('party', '=', party))
        return Payment.search(domain)


class BankAccountNumber:
    'Bank Account Number'
    __name__ = 'bank.account.number'

    mandates = fields.One2Many('account.payment.sepa.mandate',
        'account_number', 'Sepa Mandates', states={
            'invisible': Eval('type') != 'iban',
            'readonly': True},
        domain=[('party.bank_accounts', '=', Eval('account'))],
        depends=['account'])

    def objects_using_me_for_party(self, party=None):
        objects = super(BankAccountNumber, self).objects_using_me_for_party(
            party)
        if objects:
            return objects
        for m in self.mandates:
            objects = m.objects_using_me_for_party(party)
            if objects:
                return objects

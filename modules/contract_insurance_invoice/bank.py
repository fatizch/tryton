# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool


__all__ = [
    'BankAccount',
    ]


class BankAccount:
    __metaclass__ = PoolMeta
    __name__ = 'bank.account'

    def objects_using_me_for_party(self, party=None):
        objects = super(BankAccount, self).objects_using_me_for_party(party)
        if objects:
            return objects
        BillingInformation = Pool().get('contract.billing_information')
        domain = [('direct_debit_account', '=', self)]
        if party:
            domain.append(('payer', '=', party))
        return BillingInformation.search(domain)

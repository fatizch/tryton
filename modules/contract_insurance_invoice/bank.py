from trytond.pool import PoolMeta, Pool


__metaclass__ = PoolMeta
__all__ = [
    'BankAccount',
    ]


class BankAccount:
    __name__ = 'bank.account'

    def objects_using_me_for_party(self, party=None):
        objects = super(BankAccount, self).objects_using_me_for_party(party)
        if objects:
            return objects
        BillingInformation = Pool().get('contract.billing_information')
        domain = [('direct_debit_account', '=', self)]
        if party:
            domain.append(('contract.subscriber', '=', party))
        return BillingInformation.search(domain)

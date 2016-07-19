# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool


__metaclass__ = PoolMeta
__all__ = [
    'Mandate',
    ]


class Mandate:
    __name__ = 'account.payment.sepa.mandate'

    def objects_using_me_for_party(self, party=None):
        objects = super(Mandate, self).objects_using_me_for_party(party)
        if objects:
            return objects
        pool = Pool()
        BillingInformation = pool.get('contract.billing_information')
        Invoice = pool.get('account.invoice')
        domain = [('sepa_mandate', '=', self)]
        if party:
            domain.append(('payer', '=', party))
        objects = BillingInformation.search(domain)
        if objects:
            return objects
        domain = [('sepa_mandate', '=', self)]
        if party:
            domain.append(('party', '=', party))
        return Invoice.search(domain)

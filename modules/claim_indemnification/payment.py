# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool


__all__ = [
    'Payment',
    ]


class Payment:
    __metaclass__ = PoolMeta
    __name__ = 'account.payment'

    @classmethod
    def succeed(cls, payments):
        super(Payment, cls).succeed(payments)
        parties = list({x.party for x in payments if not x.line.reconciliation
            and x.kind == 'payable' and x.line.origin and
            x.line.origin.__name__ == 'account.invoice' and
            x.line.origin.business_kind == 'claim_invoice'})
        if parties:
            Pool().get('party.party').reconcile(parties)

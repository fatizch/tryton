# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool


__all__ = [
    'Payment',
    'PaymentCreation',
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


class PaymentCreation:
    __metaclass__ = PoolMeta
    __name__ = 'account.payment.creation'

    @classmethod
    def get_possible_journals(cls, lines, kind=None):
        '''
        Here, we return only one possible journal (Journal mix is not allowed
        because the related product defines the payment journal to use)
        '''
        if not any(x._line_from_claim_invoices() for x in lines):
            return super(PaymentCreation, cls).get_possible_journals(lines,
                kind)
        Line = Pool().get('account.move.line')
        payment_journals = Line.get_configuration_journals_from_lines(lines)
        if payment_journals:
            return [payment_journals[0]] if payment_journals else []
        return []

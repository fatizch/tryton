# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.model import ModelView, Workflow


__all__ = [
    'Payment',
    ]


class Payment:
    __metaclass__ = PoolMeta
    __name__ = 'account.payment'

    def create_clearing_move(self, date=None):
        move = super(Payment, self).create_clearing_move(date)
        if move:
            for line in move.lines:
                if getattr(line, 'party', None):
                    line.contract = self.line.contract
        return move

    @classmethod
    @ModelView.button
    @Workflow.transition('succeeded')
    def succeed(cls, payments):
        '''
        Launch contract reconcile if payment line invoice is cancelled
        '''
        Contract = Pool().get('contract')

        super(Payment, cls).succeed(payments)

        contracts = {p.line.contract for p in payments if p.line
            and p.line.contract and ((p.line.move.invoice and
                    p.line.move.invoice.state == 'cancel') or
                not p.line.reconciliation)}
        if contracts:
            Contract.reconcile(list(contracts))

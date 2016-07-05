# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

__metaclass__ = PoolMeta

__all__ = [
    'MoveLine',
    ]


class MoveLine:
    __name__ = 'account.move.line'

    def new_payment(self, journal, kind, amount):
        payment = super(MoveLine, self).new_payment(journal, kind, amount)
        if kind != 'payable' or journal.process_method == 'manual':
            return payment
        bank_account = self.party.get_bank_account(payment['date'])
        if bank_account:
            payment['bank_account'] = bank_account
        return payment

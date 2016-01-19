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
        bank_accounts = self.party.get_bank_accounts(payment['date'])
        if bank_accounts:
            payment['bank_account'] = bank_accounts[0]
        return payment

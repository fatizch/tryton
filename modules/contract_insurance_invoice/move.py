from trytond.pool import PoolMeta, Pool

__metaclass__ = PoolMeta

__all__ = [
    'MoveLine',
    ]


class MoveLine:
    __name__ = 'account.move.line'

    def init_payment(self, journal):
        if self.debit > 0:
            kind = 'receivable'
            payment_amount = self.debit
        elif self.credit > 0:
            kind = 'payable'
            payment_amount = self.credit
        else:
            return None
        return {
            'company': self.account.company.id,
            'kind': kind,
            'journal': journal.id,
            'party': self.party.id,
            'amount': payment_amount,
            'line': self.id,
            'date': self.payment_date,
            'state': 'approved',
            }

    @classmethod
    def create_payments(cls, lines):
        pool = Pool()
        Payment = pool.get('account.payment')
        AccountConfiguration = pool.get('account.configuration')

        payments = []
        account_configuration = AccountConfiguration(1)
        journal = account_configuration.direct_debit_journal
        if journal is None:
            return None

        for line in lines:
            payment = line.init_payment(journal)
            if not payment:
                continue
            payments.append(payment)

        Payment.create(payments)

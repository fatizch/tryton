from trytond.pool import PoolMeta, Pool

__metaclass__ = PoolMeta

__all__ = [
    'MoveLine',
    ]


class MoveLine:
    __name__ = 'account.move.line'

    def new_payment(self, journal, kind, amount):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        payment = super(MoveLine, self).new_payment(journal, kind, amount)
        if (self.origin and isinstance(self.origin, Invoice) and
                self.origin.sepa_mandate):
            payment['sepa_mandate'] = self.origin.sepa_mandate.id
        return payment

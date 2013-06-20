from trytond.pool import Pool, PoolMeta


__all__ = ['Company']
__metaclass__ = PoolMeta


class Company:
    __name__ = 'company.company'

    def get_payment_journal(self, currency):
        pool = Pool()
        PaymentJournal = pool.get('account.payment.journal')

        # XXX define a better way
        journal, = PaymentJournal.search([
                ('currency', '=', currency.id),
                ], limit=1)
        return journal

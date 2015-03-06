from trytond.pool import PoolMeta, Pool

__metaclass__ = PoolMeta

__all__ = [
    'MoveLine',
    ]


class MoveLine:
    __name__ = 'account.move.line'

    def init_payment(self, journal=None):
        AccountInvoice = Pool().get('account.invoice')
        res = super(MoveLine, self).init_payment(journal)
        if (self.origin and isinstance(self.origin, AccountInvoice) and
                self.origin.sepa_mandate):
            res['sepa_mandate'] = self.origin.sepa_mandate
        return res

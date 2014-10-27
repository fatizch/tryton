from trytond.pool import PoolMeta, Pool

__metaclass__ = PoolMeta

__all__ = [
    'MoveLine',
    ]


class MoveLine:
    __name__ = 'account.move.line'

    def init_payment(self, journal):
        AccountInvoice = Pool().get('account.invoice')
        res = super(MoveLine, self).init_payment(journal)
        if (self.origin and isinstance(self.origin, AccountInvoice) and
                self.origin.sepa_mandate):
            res['sepa_mandate'] = self.origin.sepa_mandate
            res['sepa_mandate_sequence_type'] = \
                self.origin.sepa_mandate.sequence_type
        return res

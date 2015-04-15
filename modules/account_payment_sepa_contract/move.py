from trytond.pool import PoolMeta, Pool

__metaclass__ = PoolMeta

__all__ = [
    'MoveLine',
    ]


class MoveLine:
    __name__ = 'account.move.line'

    @classmethod
    def init_payments(cls, lines, journal):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        Line = pool.get('account.move.line')
        payments = super(MoveLine, cls).init_payments(lines, journal)
        for payment in payments:
            line = Line(payment['line'])
            if (line.origin and isinstance(line.origin, Invoice) and
                    line.origin.sepa_mandate):
                payment['sepa_mandate'] = line.origin.sepa_mandate.id
        return payments

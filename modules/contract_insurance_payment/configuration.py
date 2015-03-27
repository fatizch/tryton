from trytond.pool import PoolMeta

__metaclass__ = PoolMeta
__all__ = [
    'Configuration',
    ]


class Configuration:
    __name__ = 'account.configuration'

    def get_payment_journal(self, line):
        if line.contract and line.contract.product.payment_journal:
            return line.contract.product.payment_journal
        return super(Configuration, self).get_payment_journal(line)

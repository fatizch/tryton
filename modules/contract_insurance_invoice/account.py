from trytond.pool import PoolMeta

__metaclass__ = PoolMeta
__all__ = [
    'Fee',
    ]


class Fee:
    __name__ = 'account.fee'

    def get_account_for_billing(self, line):
        return self.product.template.account_revenue_used

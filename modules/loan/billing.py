from trytond.pool import PoolMeta

__metaclass__ = PoolMeta
__all__ = [
    'BillingPremium'
    ]


class BillingPremium:
    __name__ = 'contract.billing.premium'

    @classmethod
    def get_line_target_models(cls):
        result = super(BillingPremium, cls).get_line_target_models()
        result.append(('loan.share', 'loan.share'))
        return result

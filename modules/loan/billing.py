from trytond.pool import PoolMeta

__metaclass__ = PoolMeta
__all__ = [
    'LoanPriceLine'
    ]


class LoanPriceLine():
    'Loan Price Line'

    __name__ = 'contract.billing.premium'

    @classmethod
    def get_line_target_models(cls):
        result = super(LoanPriceLine, cls).get_line_target_models()
        result.append(('loan.share', 'loan.share'))
        return result

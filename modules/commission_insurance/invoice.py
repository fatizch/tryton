from dateutil.relativedelta import relativedelta
from decimal import Decimal

from trytond.pool import PoolMeta

__all__ = [
    'InvoiceLine',
    ]
__metaclass__ = PoolMeta


class InvoiceLine:
    __name__ = 'account.invoice.line'

    @classmethod
    def __setup__(cls):
        super(InvoiceLine, cls).__setup__()
        cls.account.domain.pop(1)

    def _get_commission_amount(self, amount, plan, pattern=None):
        coverage = getattr(self.details[0], 'coverage', None)
        option = getattr(self.details[0], 'option', None)
        if coverage and option:
            delta = relativedelta(self.coverage_start,
                option.start_date)
            pattern = {
                'option': coverage,
                'nb_years': delta.years
                }
        commission_amount = plan.compute(amount, self.product, pattern)
        if commission_amount:
            return commission_amount.quantize(
                Decimal(str(10.0 ** -self.currency_digits)))

# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from dateutil import rrule

from trytond.pool import PoolMeta

__all__ = [
    'ProductPremiumDate',
    ]


class ProductPremiumDate(metaclass=PoolMeta):
    __name__ = 'offered.product.premium_date'

    @classmethod
    def __setup__(cls):
        super(ProductPremiumDate, cls).__setup__()
        cls.type_.selection.append(
            ('yearly_at_loan_anniversary_date',
                'Yearly At Loan Anniversary Date'))

    def get_rule_for_contract(self, contract):
        if self.type_ != 'yearly_at_loan_anniversary_date':
            return super(ProductPremiumDate, self).get_rule_for_contract(
                contract)
        ruleset = rrule.rruleset()
        for loan in contract.loans:
            ruleset.rrule(rrule.rrule(rrule.YEARLY,
                dtstart=loan.funds_release_date, until=loan.end_date,
                bymonthday=loan.funds_release_date.day,
                bymonth=loan.funds_release_date.month))
        return ruleset

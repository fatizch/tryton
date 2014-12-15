from dateutil import rrule

from trytond.pool import PoolMeta
from trytond.modules.cog_utils import fields

__metaclass__ = PoolMeta

__all__ = [
    'ProductPremiumDates',
    ]


class ProductPremiumDates:
    __name__ = 'offered.product.premium_dates'

    yearly_each_covered_anniversary_date = fields.Boolean('Yearly Each '
        'Covered Anniversary Date')

    def get_dates_for_contract(self, contract):
        res = super(ProductPremiumDates, self).get_dates_for_contract(
            contract)
        max_date = contract.end_date or contract.next_renewal_date
        if not max_date:
            return res
        ruleset = rrule.rruleset()
        if self.yearly_each_covered_anniversary_date:
            for covered_element in contract.covered_elements:
                if not covered_element.party or not covered_element.is_person:
                    continue
                ruleset.rrule(rrule.rrule(rrule.YEARLY,
                    dtstart=contract.start_date, until=max_date,
                    bymonthday=covered_element.party.birth_date.day,
                    bymonth=covered_element.party.birth_date.month))
            res.extend([x.date() for x in ruleset])
        return res

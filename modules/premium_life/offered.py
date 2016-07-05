# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from dateutil import rrule

from trytond.pool import PoolMeta

__metaclass__ = PoolMeta

__all__ = [
    'ProductPremiumDate',
    ]


class ProductPremiumDate:
    __name__ = 'offered.product.premium_date'

    @classmethod
    def __setup__(cls):
        super(ProductPremiumDate, cls).__setup__()
        cls.type_.selection.append(
            ('yearly_each_covered_anniversary_date',
                'Yearly Each Covered Anniversary Date'))

    def get_rule_for_contract(self, contract):
        res = super(ProductPremiumDate, self).get_rule_for_contract(contract)
        if res:
            return res
        max_date = contract.end_date
        if not max_date:
            return res
        if self.type_ == 'yearly_each_covered_anniversary_date':
            ruleset = rrule.rruleset()
            for covered_element in contract.covered_elements:
                if not covered_element.party or not covered_element.is_person:
                    continue
                ruleset.rrule(rrule.rrule(rrule.YEARLY,
                    dtstart=contract.start_date, until=max_date,
                    bymonthday=covered_element.party.birth_date.day,
                    bymonth=covered_element.party.birth_date.month))
            return ruleset

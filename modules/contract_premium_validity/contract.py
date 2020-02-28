# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from dateutil.relativedelta import relativedelta

from trytond.pool import PoolMeta

from trytond.modules.coog_core import fields, utils

__all__ = [
    'Contract',
    ]


class Contract(metaclass=PoolMeta):
    __name__ = 'contract'

    premium_validity_end = fields.Date('Premium Validity End', readonly=True,
        help='Defines the date at which the premiums on the contract will stop'
        ' being valid')

    @classmethod
    def calculate_prices(cls, contracts, start=None, end=None):
        cls.update_premium_validity_date(contracts)
        to_calculate = [x for x in contracts if
            not x.premium_validity_end or not start or (start
                and x.premium_validity_end > start)]
        super().calculate_prices(to_calculate, start, end)

    @classmethod
    def update_premium_validity_date(cls, contracts):
        to_save = []
        for contract in contracts:
            if contract.product.premium_ending_rule:
                validity_rule = contract.product.premium_ending_rule[0]
                context = {'date': utils.today()}
                contract.init_dict_for_rule_engine(context)
                end_date = validity_rule.calculate_rule(context)
                if (not contract.premium_validity_end) or \
                        contract.premium_validity_end < end_date:
                    contract.premium_validity_end = end_date
                    to_save.append(contract)
        if to_save:
            cls.save(contracts)

    def limit_dates(self, dates, start=None, end=None):
        premium_end = self.premium_validity_end
        end = premium_end + relativedelta(days=1) if premium_end else end
        return super().limit_dates(dates, start, end)

# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.modules.cog_utils import coop_date

__metaclass__ = PoolMeta
__all__ = [
    'BenefitRule',
    ]


class BenefitRule:
    __name__ = 'benefit.rule'

    def get_indemnification_end_date(self, from_date, to_date, args):
        if 'loan' not in args:
            return super(BenefitRule, self(from_date, to_date, args))
        loan = args['loan']
        if loan:
            payment = loan.get_payment(from_date)
            return min(to_date, coop_date.get_end_of_period(payment.start_date,
                    loan.payment_frequency))
        else:
            return

    def get_unit_per_period(self, start_date, end_date, args):
        if 'loan' not in args:
            return super(BenefitRule, self).get_unit_per_period(start_date,
                end_date, args)
        if 'payment' not in args:
            return None, None
        payment = args['payment']
        nb = 0
        if start_date <= payment.start_date <= end_date:
            nb = 1
        return nb, args['loan'].payment_frequency

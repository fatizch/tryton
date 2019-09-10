# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import PoolMeta

__all__ = [
    'InvoiceLineWithLoan',
    ]


class InvoiceLineWithLoan(metaclass=PoolMeta):
    __name__ = 'account.invoice.line'

    def _get_commission_pattern(self, plan, agent, start, end):
        pattern = super(InvoiceLineWithLoan, self)._get_commission_pattern(
            plan, agent, start, end)
        if self.details:
            option = self.details[0].get_option()
            shares = [x for x in option.get_shares_at_date(
                start) if x.loan.id == self.details[0].loan.id]
            if shares:
                pattern['loan_share'] = shares[0]
        return pattern

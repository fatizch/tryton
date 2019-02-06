# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal

from trytond.pool import PoolMeta


__all__ = [
    'Invoice',
    ]


class Invoice(metaclass=PoolMeta):
    __name__ = 'contract.invoice'

    def _check_rsi_invoice_date(self, period_start, period_end):
        if self.invoice_state != 'paid':
            date_to_check = self.start
        else:
            date_to_check = self.invoice.reconciliation_date

        if date_to_check and date_to_check >= period_start and \
                date_to_check <= period_end and \
                self._positive_subscriber_dependent_amount():
            return True
        return False

    def _positive_subscriber_dependent_amount(self):
        amount = Decimal('0')
        for line in self.invoice.lines:
            if line.covered_element and (
                    line.covered_element.party.main_insured_ssn ==
                    self.contract.subscriber.ssn or
                    line.covered_element.party == self.contract.subscriber):
                amount += line.amount
        return amount

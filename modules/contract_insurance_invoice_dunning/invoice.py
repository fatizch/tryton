# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from trytond.pool import PoolMeta
from trytond.server_context import ServerContext


__all__ = [
    'Invoice',
    ]


class Invoice:
    __metaclass__ = PoolMeta
    __name__ = 'account.invoice'

    def get_dunning_procedure(self):
        if self.contract and self.contract.product.dunning_procedure:
            return self.contract.product.dunning_procedure
        return self.party.dunning_procedure

    def get_move(self):
        move = super(Invoice, self).get_move()
        if ServerContext().get('default_maturity_date', False) \
                or not self.contract_invoice:
            return move
        if any(getattr(l, 'payment_date', None) for l in move.lines):
            dunning_procedure = self.get_dunning_procedure()
            if dunning_procedure and dunning_procedure.from_payment_date:
                for line in move.lines:
                    if getattr(line, 'payment_date', None):
                        line.maturity_date = line.payment_date

                cancelled = self.get_cancelled_in_rebill()

                if not cancelled:
                    return move

                def date_key(line):
                    return line.maturity_date or datetime.date.min

                old_lines_to_pay = sorted(cancelled.invoice.lines_to_pay,
                    key=date_key)
                lines_to_pay = sorted([x for x in move.lines if
                        x.account == self.account], key=date_key)
                if cancelled.invoice.payment_term == self.payment_term and \
                        len(lines_to_pay) == len(old_lines_to_pay):
                    for old, new in zip(old_lines_to_pay, lines_to_pay):
                        new.maturity_date = old.maturity_date
                move.lines = move.lines
        return move

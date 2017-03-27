# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
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

    def _get_move_line(self, date, amount):
        line = super(Invoice, self)._get_move_line(date, amount)
        if ServerContext().get('default_maturity_date', False):
            return line
        if getattr(line, 'payment_date', None):
            dunning_procedure = self.get_dunning_procedure()
            if dunning_procedure and dunning_procedure.from_payment_date:
                line.maturity_date = line.payment_date
        return line

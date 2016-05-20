from trytond.pool import PoolMeta

__metaclass__ = PoolMeta
__all__ = [
    'Invoice',
    ]


class Invoice:
    __name__ = 'account.invoice'

    def get_dunning_procedure(self):
        if self.contract and self.contract.product.dunning_procedure:
            return self.contract.product.dunning_procedure
        return self.party.dunning_procedure

    def _get_move_line(self, date, amount):
        line = super(Invoice, self)._get_move_line(date, amount)
        if line.get('payment_date', None):
            dunning_procedure = self.get_dunning_procedure()
            if dunning_procedure and dunning_procedure.from_payment_date:
                line['maturity_date'] = line['payment_date']
        return line

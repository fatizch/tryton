from trytond.pool import PoolMeta
from trytond.model import fields

__metaclass__ = PoolMeta

__all__ = [
    'Line',
    ]


class Line:
    'Account Move Line'
    __name__ = 'account.move.line'

    reconciliation_lines = fields.Function(
        fields.One2Many('account.move.line', 'reconciliation_lines',
            'Reconciliation Lines'),
        'get_reconciliation_lines')
    currency_symbol = fields.Function(
        fields.Char('Currency Symbol'), 'get_currency_symbol')

    def get_synthesis_rec_name(self, name):
        if self.origin:
            if (getattr(self.origin, 'get_synthesis_rec_name', None)
                    is not None):
                return self.origin.get_synthesis_rec_name(name)
            return self.origin.get_rec_name(name)
        return self.get_rec_name(name)

    def get_reconciliation_lines(self, name):
        if self.reconciliation is None:
            return
        return[line.id for line in self.reconciliation.lines]

    def get_currency_symbol(self, name):
        return self.account.currency.symbol if self.account else ''

    def get_icon(self, name=None):
        if self.reconciliation:
            return 'coopengo-reconciliation'

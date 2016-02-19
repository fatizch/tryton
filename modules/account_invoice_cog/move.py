from trytond.pool import PoolMeta
from trytond.modules.cog_utils import fields

__metaclass__ = PoolMeta
__all__ = [
    'Move',
    'MoveLine',
    ]


class Move:
    __name__ = 'account.move'

    is_invoice_canceled = fields.Function(
        fields.Boolean('Invoice Canceled'),
        'get_is_invoice_canceled')

    def get_is_invoice_canceled(self, name):
        return (self.is_origin_canceled and self.origin_item
            and self.origin_item.__name__ == 'account.invoice')


class MoveLine:
    __name__ = 'account.move.line'

    is_invoice_canceled = fields.Function(
        fields.Boolean('Invoice Canceled'),
        'get_move_field')

    def get_color(self, name):
        if self.is_invoice_canceled:
            return 'grey'
        color = super(MoveLine, self).get_color(name)
        amount = getattr(self.move.origin_item, 'total_amount', None)
        return 'red' if color == 'black' and amount < 0 else color

from dateutil.relativedelta import relativedelta
from decimal import Decimal

from trytond.pool import PoolMeta

from trytond.modules.cog_utils import utils, fields

__all__ = [
    'InvoiceLine',
    'Invoice',
    ]
__metaclass__ = PoolMeta


class InvoiceLine:
    __name__ = 'account.invoice.line'

    @classmethod
    def __setup__(cls):
        super(InvoiceLine, cls).__setup__()
        cls.account.domain.pop(1)

    def _get_commission_amount(self, amount, plan, pattern=None):
        if getattr(self, 'details', None):
            option = self.details[0].get_option()
            if option:
                delta = relativedelta(self.coverage_start,
                    option.start_date)
                pattern = {
                    'option': option.coverage,
                    'nb_years': delta.years
                    }
        commission_amount = plan.compute(amount, self.product, pattern)
        if commission_amount:
            return commission_amount.quantize(
                Decimal(str(10.0 ** -self.currency_digits)))


class Invoice:
    __name__ = 'account.invoice'

    is_commission_invoice = fields.Function(
        fields.Boolean('Is Commission Invoice'),
        'get_is_commission_invoice')

    def _get_move_line(self, date, amount):
        line = super(Invoice, self)._get_move_line(date, amount)
        if self.is_commission_invoice:
            line['payment_date'] = utils.today()
        return line

    def get_is_commission_invoice(self, name):
        return self.party.is_broker and self.type == 'in_invoice'

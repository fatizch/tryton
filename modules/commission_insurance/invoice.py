from dateutil.relativedelta import relativedelta
from decimal import Decimal

from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.cog_utils import utils, fields

__all__ = [
    'InvoiceLine',
    'Invoice',
    ]
__metaclass__ = PoolMeta


class InvoiceLine:
    __name__ = 'account.invoice.line'

    broker_fee_lines = fields.One2Many('account.move.line',
        'broker_fee_invoice_line', 'Broker Fee Lines', readonly=True,
        states={'invisible': ~Eval('broker_fee_lines')})

    @classmethod
    def __setup__(cls):
        super(InvoiceLine, cls).__setup__()
        cls.account.domain.pop(1)
        cls._error_messages.update({
                'no_broker_define_for_broker_fee': 'No broker define on '
                'contract %s for broker fee %s'
                })

    def _get_commission_amount(self, amount, plan, pattern=None):
        pattern = {}
        if getattr(self, 'details', None):
            option = self.details[0].get_option()
            if option:
                delta = relativedelta(self.coverage_start,
                    option.start_date)
                pattern = {
                    'coverage': option.coverage,
                    'option': option,
                    'nb_years': delta.years
                    }
        pattern['invoice_line'] = self
        commission_amount = plan.compute(amount, self.product, pattern)
        if commission_amount:
            return commission_amount.quantize(
                Decimal(str(10.0 ** -self.currency_digits)))

    def get_move_line(self):
        lines = super(InvoiceLine, self).get_move_line()
        if (not self.account.party_required or not self.invoice.contract or
                not getattr(self.detail, 'fee', None) or
                not self.detail.fee.broker_fee):
            return lines
        if not self.invoice.contract.agent:
            self.raise_user_error('no_broker_define_for_broker_fee',
                self.invoice.contract, self.details.fee.rec_name)
        # Update party to broker for broker fee line
        for line in lines:
            line['party'] = self.invoice.contract.agent.party
        return lines


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

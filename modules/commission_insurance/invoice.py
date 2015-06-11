from dateutil.relativedelta import relativedelta
from decimal import Decimal

from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.model import ModelView, Workflow
from trytond.tools import grouped_slice

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

    def get_commissions(self):
        # Total override of tryton method just to add the agent parameter to
        # _get_commission_amount
        pool = Pool()
        Commission = pool.get('commission')
        Currency = pool.get('currency.currency')
        Date = pool.get('ir.date')

        if self.type != 'line':
            return []

        today = Date.today()
        commissions = []
        for agent, plan in self.agent_plans_used:
            if not plan:
                continue
            with Transaction().set_context(date=self.invoice.currency_date):
                amount = Currency.compute(self.invoice.currency,
                    self.amount, agent.currency, round=False)
            if self.invoice.type == 'out_credit_note':
                amount *= -1
            commission_amount = self._get_commission_amount(amount, plan,
                agent=agent)
            if commission_amount:
                commission_rate = (commission_amount / amount * 100).quantize(
                    Decimal('.01'))
                commission_amount = commission_amount.quantize(Decimal(str(
                            10.0 ** -self.currency_digits)))
            if not commission_amount:
                continue

            commission = Commission()
            commission.origin = self
            if plan.commission_method == 'posting':
                commission.date = today
            commission.agent = agent
            commission.product = plan.commission_product
            commission.amount = commission_amount
            commission.commission_rate = commission_rate
            commissions.append(commission)
        return commissions

    def _get_commission_amount(self, amount, plan, pattern=None, agent=None):
        pattern = {}
        if getattr(self, 'details', None):
            option = self.details[0].get_option()
            if option:
                delta = relativedelta(self.coverage_start,
                    option.start_date)
                pattern = {
                    'coverage': option.coverage,
                    'option': option,
                    'nb_years': delta.years,
                    'agent': agent,
                    'plan': plan,
                    }
        pattern['invoice_line'] = self
        commission_amount = plan.compute(amount, self.product, pattern)
        return commission_amount

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

    @classmethod
    @ModelView.button
    @Workflow.transition('cancel')
    def cancel(cls, invoices):
        pool = Pool()
        Commission = pool.get('commission')
        MoveLine = pool.get('account.move.line')

        super(Invoice, cls).cancel(invoices)

        for sub_invoices in grouped_slice(invoices):
            # Remove link to invoice_line in commission for cancelled invoice
            ids = [i.id for i in sub_invoices]
            commissions = Commission.search([
                    ('invoice_line.invoice', 'in', ids)
                    ])
            Commission.write(commissions, {'invoice_line': None})
            # Remove link to invoice_line in move link to a broker fee
            move_lines = MoveLine.search([
                    ('broker_fee_invoice_line.invoice', 'in', ids)
                    ])
            MoveLine.write(move_lines, {'broker_fee_invoice_line': None})

# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from sql import Cast, Null, Literal

from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, Or, In
from trytond.transaction import Transaction
from trytond.model import ModelView, Workflow
from trytond.tools import grouped_slice

from trytond.modules.coog_core import utils, fields, coog_date, coog_sql
from .commission import COMMISSION_AMOUNT_DIGITS, COMMISSION_RATE_DIGITS

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
        cls.quantity.states['invisible'] = ~Eval('unit')
        cls.quantity.depends += ['unit']
        cls.unit_price.states['invisible'] = ~Eval('unit')
        cls.unit_price.depends += ['unit']
        cls.unit.states['invisible'] = ~Eval('unit')
        cls.principal.readonly = True
        cls.account.domain.pop(1)
        cls._error_messages.update({
                'no_broker_define_for_broker_fee': 'No broker define on '
                'contract %s for broker fee %s'
                })

    @classmethod
    def __register__(cls, module_name):
        super(InvoiceLine, cls).__register__(module_name)
        utils.add_reference_index(cls, module_name)

    def get_commissions(self):
        # Total override of tryton method just to add the agent parameter to
        # _get_commission_amount and to set commissioned_option
        if not self.details or not self.details[0].get_option():
            # Not a contract line
            return super(InvoiceLine, self).get_commissions()

        if self.type != 'line':
            return []

        commissions = []
        for agent, plan in self.agent_plans_used:
            if not plan:
                continue
            commissions += self.get_commissions_for_agent(agent, plan)
        return commissions

    def get_commissions_for_agent(self, agent, plan):
        pool = Pool()
        Commission = pool.get('commission')
        Currency = pool.get('currency.currency')
        Date = pool.get('ir.date')

        today = Date.today()
        with Transaction().set_context(date=self.invoice.currency_date):
            base_amount = Currency.compute(self.invoice.currency,
                self.amount, agent.currency, round=False)
        if self.invoice.type == 'out_credit_note':
            base_amount *= -1
        commission_data = []
        for start, end in plan.get_commission_periods(self):
            amount = base_amount * (Decimal((end - start).days + 1) /
                Decimal((self.coverage_end - self.coverage_start).days + 1))
            commission_amount = self._get_commission_amount(amount, plan,
                pattern={'agent': agent, 'date_start': start, 'date_end': end})
            if not commission_amount:
                continue
            commission_rate = (commission_amount / amount).quantize(
                Decimal(10) ** -COMMISSION_RATE_DIGITS)
            if (commission_data and commission_data[-1][3] == commission_rate
                    and commission_data[-1][1] == coog_date.add_day(
                        start, -1)):
                # Same rate => extend previous line
                commission_data[-1][1] = end
                commission_data[-1][2] += commission_amount
            else:
                commission_data.append([start, end, commission_amount,
                        commission_rate])

        commissions = []
        for start, end, commission_amount, commission_rate in commission_data:
            commission_amount = commission_amount.quantize(
                Decimal(10) ** -COMMISSION_AMOUNT_DIGITS)
            if not commission_amount:
                continue
            commission = Commission()
            commission.origin = self
            if plan.commission_method == 'posting':
                commission.date = today
            commission.start = start
            commission.end = end
            commission.agent = agent
            commission.product = plan.commission_product
            commission.amount = commission_amount
            commission.commission_rate = commission_rate
            commission.commissioned_option = self.details[0].get_option()
            commissions.append(commission)
        return commissions

    def _get_commission_amount(self, amount, plan, pattern=None):
        product = self.product
        if self.details:
            option = self.details[0].get_option()
            if option:
                assert pattern and 'date_start' in pattern
                delta = relativedelta(pattern['date_start'],
                    option.start_date)
                pattern.update({
                        'coverage': option.coverage,
                        'option': option,
                        'nb_years': delta.years,
                        'plan': plan,
                        'invoice_line': self,
                        })
            elif self.details[0].fee and not product:
                product = self.details[0].fee.product
        commission_amount = plan.compute(amount, product, pattern)
        return commission_amount

    def get_move_lines(self):
        lines = super(InvoiceLine, self).get_move_lines()
        if (not self.account.party_required or not self.invoice.contract or
                not getattr(self.detail, 'fee', None) or
                not self.detail.fee.broker_fee):
            return lines
        if not self.invoice.contract.agent:
            self.raise_user_error('no_broker_define_for_broker_fee',
                self.invoice.contract, self.details.fee.rec_name)
        # Update party to broker for broker fee line
        for line in lines:
            line.party = self.invoice.contract.agent.party
        return lines


class Invoice:
    __name__ = 'account.invoice'

    @classmethod
    def __setup__(cls):
        super(Invoice, cls).__setup__()
        cls.business_kind.selection += [
            ('broker_invoice', 'Broker Invoice'),
            ('insurer_invoice', 'Insurer Invoice'),
            ]
        for field in ('taxes', 'tax_amount', 'untaxed_amount'):
            getattr(cls, field).states = {
                'invisible': Or(In(Eval('business_kind'),
                        ['insurer_invoice', 'broker_invoice']),
                    getattr(cls, field).states.get('invisible', False)),
                }
            getattr(cls, field).depends += ['business_kind']

    @classmethod
    def __register__(cls, module_name):
        pool = Pool()
        super(Invoice, cls).__register__(module_name)
        # Migration from 1.6 Store Business Kind
        cursor = Transaction().connection.cursor()
        invoice = cls.__table__()
        to_update = cls.__table__()
        insurer = pool.get('insurer').__table__()
        network = pool.get('distribution.network').__table__()

        query = invoice.join(insurer,
            condition=invoice.party == insurer.party
            ).select(invoice.id,
            where=((invoice.business_kind == Null)
                & (invoice.type == 'in')))
        cursor.execute(*to_update.update(
                columns=[to_update.business_kind],
                values=[Literal('insurer_invoice')],
                where=to_update.id.in_(query)))

        query2 = invoice.join(network,
            condition=invoice.party == network.party
            ).select(invoice.id,
            where=((invoice.business_kind == Null)
                & (invoice.type == 'in')))
        cursor.execute(*to_update.update(
                columns=[to_update.business_kind],
                values=[Literal('broker_invoice')],
                where=to_update.id.in_(query2)))

    def _get_move_line(self, date, amount):
        line = super(Invoice, self)._get_move_line(date, amount)
        if (getattr(self, 'business_kind', None) in
                ['insurer_invoice', 'broker_invoice'] and
                self.type == 'in' and self.total_amount > 0):
            line.payment_date = line.maturity_date or utils.today()
        return line

    def get_synthesis_rec_name(self, name):
        Date = Pool().get('ir.date')
        if self.business_kind not in ['insurer_invoice', 'broker_invoice']:
            return super(Invoice, self).get_synthesis_rec_name(name)
        return '%s %s [%s]' % (self.business_kind_string,
            Date.date_as_string(self.invoice_date),
            self.state_string)

    @classmethod
    def _get_commissions_to_delete(cls, ids):
        # Never delete commissions, #3261
        return []

    @classmethod
    def _get_commissions_to_cancel(cls, ids):
        # Override for performance : the domain resolution of the
        # field reference `origin` is not optimized for big databases
        # and takes a while to be executed as query.
        #
        # All commissions should be canceled, even though they are not yet in
        # an invoice #3261
        pool = Pool()
        Commission = pool.get('commission')
        InvoiceLine = pool.get('account.invoice.line')
        commission = Commission.__table__()
        invoice_line = InvoiceLine.__table__()
        cursor = Transaction().connection.cursor()

        sub_query = invoice_line.select(
            coog_sql.TextCat('account.invoice.line,',
                Cast(invoice_line.id, 'VARCHAR')),
            where=invoice_line.invoice.in_(ids))

        cursor.execute(*commission.select(commission.id, where=(
                    commission.origin.in_(sub_query))))
        return Commission.browse([x[0] for x in cursor.fetchall()])

    @classmethod
    @ModelView.button
    @Workflow.transition('posted')
    def post(cls, invoices):
        # Cancel and recreate commissions for invoices that were paid
        paid_invoices = [i for i in invoices if i.state == 'paid']
        super(Invoice, cls).post(invoices)

        if paid_invoices:
            cls.reset_commissions(paid_invoices)

    @classmethod
    def reset_commissions(cls, invoices):
        pool = Pool()
        Commission = pool.get('commission')
        clear_date, cancel = [], []
        for invoice in invoices:
            for line in invoice.lines:
                for commission in line.commissions:
                    if commission.date and not commission.invoice_line:
                        clear_date.append(commission)
                    elif commission.invoice_line:
                        # TODO : Somehow manage to filter out already reset /
                        # canceled lines. Right now, unpaying will generate two
                        # lines (3 with the original line), unpaying again will
                        # generate 9, unpaying again 27 etc...
                        cancel.append(commission)

        # Reset date of not paid commissions, so that they will not be paid
        # until the invoice is properly paid again
        if clear_date:
            Commission.write(clear_date, {'date': None})
        if not cancel:
            return

        # Cancel commissions
        cancel_commissions = Commission.cancel(cancel)

        # Make another copy which will be available to be paid, once the
        # client invoice is re-paid.
        new_commissions = Commission.copy(cancel_commissions, {'date': None})
        for com in new_commissions:
            com.amount *= -1
        Commission.save(new_commissions)

    @classmethod
    @ModelView.button
    @Workflow.transition('cancel')
    def cancel(cls, invoices):
        pool = Pool()
        Commission = pool.get('commission')
        MoveLine = pool.get('account.move.line')

        super(Invoice, cls).cancel(invoices)

        if not any(invoice.business_kind in ('broker_invoice',
                'insurer_invoice') for invoice in invoices):
            return

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

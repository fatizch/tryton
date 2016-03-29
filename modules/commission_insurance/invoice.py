from dateutil.relativedelta import relativedelta
from decimal import Decimal
from sql.operators import Concat
from sql import Cast, Null, Literal

from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, Or, In
from trytond.transaction import Transaction
from trytond.model import ModelView, Workflow
from trytond.tools import grouped_slice

from trytond.modules.cog_utils import utils, fields, coop_date

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
                Decimal('.0001'))
            if (commission_data and commission_data[-1][3] == commission_rate
                    and commission_data[-1][1] == coop_date.add_day(
                        start, -1)):
                # Same rate => extend previous line
                commission_data[-1][1] = end
                commission_data[-1][2] += commission_amount
            else:
                commission_data.append([start, end, commission_amount,
                        commission_rate])

        commissions = []
        digits = Commission.amount.digits
        for start, end, commission_amount, commission_rate in commission_data:
            commission_amount = commission_amount.quantize(
                Decimal(str(10.0 ** -digits[1])))
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

        cls._buttons.update({
                'draft': {
                    'invisible': (~Eval('business_kind').in_(
                            ['broker_invoice', 'insurer_invoice'])
                        | cls._buttons['draft']['invisible'])
                    },
                })

    @classmethod
    def __register__(cls, module_name):
        pool = Pool()
        super(Invoice, cls).__register__(module_name)
        # Migration from 1.6 Store Business Kind
        cursor = Transaction().cursor
        invoice = cls.__table__()
        to_update = cls.__table__()
        insurer = pool.get('insurer').__table__()
        network = pool.get('distribution.network').__table__()

        query = invoice.join(insurer,
            condition=invoice.party == insurer.party
            ).select(invoice.id,
            where=((invoice.business_kind == Null)
                & (invoice.type == 'in_invoice')))
        cursor.execute(*to_update.update(
                columns=[to_update.business_kind],
                values=[Literal('insurer_invoice')],
                where=to_update.id.in_(query)))

        query2 = invoice.join(network,
            condition=invoice.party == network.party
            ).select(invoice.id,
            where=((invoice.business_kind == Null)
                & (invoice.type == 'in_invoice')))
        cursor.execute(*to_update.update(
                columns=[to_update.business_kind],
                values=[Literal('broker_invoice')],
                where=to_update.id.in_(query2)))

    def _get_move_line(self, date, amount):
        line = super(Invoice, self)._get_move_line(date, amount)
        if (getattr(self, 'business_kind', None) in
                ['insurer_invoice', 'broker_invoice'] and
                self.type == 'in_invoice' and self.total_amount > 0):
            line['payment_date'] = utils.today()
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
        cursor = Transaction().cursor

        sub_query = invoice_line.select(
            Concat('account.invoice.line,', Cast(invoice_line.id, 'VARCHAR')),
            where=invoice_line.invoice.in_(ids))

        cursor.execute(*commission.select(commission.id, where=(
                    commission.origin.in_(sub_query))))
        return Commission.browse([x[0] for x in cursor.fetchall()])

    @classmethod
    def update_commission_before_cancel(cls, commissions):
        # before cancelling a commission, set the date to today
        # in order to be include the commission and his cancellation
        # in the next invoice broker
        if not commissions:
            return
        pool = Pool()
        Commission = pool.get('commission')
        commission = Commission.__table__()
        cursor = Transaction().cursor
        cursor.execute(*commission.select(commission.id, where=(
                    (commission.id.in_([c.id for c in commissions])) &
                    (commission.date == Null))))
        to_update = Commission.browse([x[0] for x in cursor.fetchall()])
        Commission.write(to_update, {'date': utils.today()})

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

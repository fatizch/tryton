from dateutil.relativedelta import relativedelta
from decimal import Decimal
from sql.operators import Concat
from sql import Cast

from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval
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
        for start, end, commission_amount, commission_rate in commission_data:
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

    is_broker_invoice = fields.Function(
        fields.Boolean('Is Broker Invoice'),
        'get_is_broker_invoice', searcher='search_is_broker_invoice')
    is_insurer_invoice = fields.Function(
        fields.Boolean('Is Insurer Invoice'),
        'get_is_insurer_invoice', searcher='search_is_insurer_invoice')

    @classmethod
    def __setup__(cls):
        super(Invoice, cls).__setup__()
        cls.business_type.selection += [
            ('broker_invoice', 'Broker Invoice'),
            ('insurer_invoice', 'Insurer Invoice'),
            ]
        cls.business_type.depends += ['is_broker_invoice',
            'is_insurer_invoice']

    def _get_move_line(self, date, amount):
        line = super(Invoice, self)._get_move_line(date, amount)
        if (getattr(self, 'is_broker_invoice', None) and
                self.type == 'in_invoice' and self.total_amount > 0):
            line['payment_date'] = utils.today()
        return line

    @classmethod
    def get_is_broker_invoice(cls, invoices, name):
        pool = Pool()
        cursor = Transaction().cursor
        invoice = pool.get('account.invoice').__table__()
        network = pool.get('distribution.network').__table__()
        result = {x.id: False for x in invoices}

        cursor.execute(*invoice.join(network,
                condition=invoice.party == network.party
                ).select(invoice.id,
                where=(invoice.id.in_([x.id for x in invoices])),
                group_by=[invoice.id]))

        for invoice_id, in cursor.fetchall():
            result[invoice_id] = True
        return result

    def get_business_type(self, name):
        if self.is_broker_invoice:
            return 'broker_invoice'
        elif self.is_insurer_invoice:
            return 'insurer_invoice'
        else:
            return super(Invoice, self).get_business_type(name)

    @classmethod
    def search_is_broker_invoice(cls, name, clause):
        if (clause[1] == '=' and clause[2] or
                clause[1] == ':=' and not clause[2]):
            return [('party.network', '!=', None)]
        else:
            return [('party.network', '=', None)]

    def get_synthesis_rec_name(self, name):
        Date = Pool().get('ir.date')
        if not self.is_broker_invoice and not self.is_insurer_invoice:
            return super(Invoice, self).get_synthesis_rec_name(name)
        return '%s %s [%s]' % (self.business_type_string,
            Date.date_as_string(self.invoice_date),
            self.state_string)

    @classmethod
    def get_is_insurer_invoice(cls, invoices, name):
        pool = Pool()
        cursor = Transaction().cursor
        invoice = pool.get('account.invoice').__table__()
        insurer = pool.get('insurer').__table__()
        result = {x.id: False for x in invoices}

        cursor.execute(*invoice.join(insurer,
                condition=invoice.party == insurer.party
                ).select(invoice.id,
                where=(invoice.id.in_([x.id for x in invoices])),
                group_by=[invoice.id]))

        for invoice_id, in cursor.fetchall():
            result[invoice_id] = True
        return result

    @classmethod
    def search_is_insurer_invoice(cls, name, clause):
        if (clause[1] == '=' and clause[2] or
                clause[1] == ':=' and not clause[2]):
            return [('party.insurer_role', '!=', None)]
        else:
            return [('party.insurer_role', '=', None)]

    @classmethod
    def _get_commissions_to_delete(cls, ids):
        # Temporary and dummy fix: the domain resolution of the
        # field reference `origin` is not optimized for big databases
        # and takes a while to be executed as query.
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
                    (commission.invoice_line == None) &
                    commission.origin.in_(sub_query))))
        return Commission.browse([x[0] for x in cursor.fetchall()])

    @classmethod
    def _get_commissions_to_cancel(cls, ids):
        # Temporary and dummy fix: the domain resolution of the
        # field reference `origin` is not optimized for big databases
        # and takes a while to be executed as query.
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
                    (commission.invoice_line != None) &
                    commission.origin.in_(sub_query))))
        return Commission.browse([x[0] for x in cursor.fetchall()])

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

# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from sql import Cast, Null, Literal
from sql.conditionals import Case
from sql.operators import Concat
from itertools import groupby

from trytond.pool import PoolMeta, Pool
from trytond import backend
from trytond.i18n import gettext
from trytond.pyson import Eval, Or, In, Not
from trytond.transaction import Transaction
from trytond.model import ModelView, Workflow
from trytond.model.exceptions import ValidationError
from trytond.server_context import ServerContext
from trytond.tools import grouped_slice
from trytond.cache import Cache

from trytond.modules.coog_core import utils, fields, coog_sql
from .commission import COMMISSION_AMOUNT_DIGITS, COMMISSION_RATE_DIGITS

__all__ = [
    'InvoiceLine',
    'Invoice',
    ]


class InvoiceLine(metaclass=PoolMeta):
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

    @classmethod
    def __register__(cls, module_name):
        super(InvoiceLine, cls).__register__(module_name)
        utils.add_reference_index(cls, module_name)

    @classmethod
    def delete(cls, invoice_lines):
        # We want to have the right to clear the 'invoice_line' field
        with ServerContext().set_context(allow_modify_commissions=True):
            super(InvoiceLine, cls).delete(invoice_lines)

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
        Currency = pool.get('currency.currency')
        with Transaction().set_context(date=self.invoice.currency_date):
            base_amount = Currency.compute(self.invoice.currency,
                self.amount, agent.currency, round=False)
        if self.invoice.type == 'out_credit_note':
            base_amount *= -1
        commissions = []
        for start, end in plan.get_commission_periods(self):
            pattern = self._get_commission_pattern(plan, agent, start, end)
            plan_line = plan.get_matching_line(pattern)
            if not plan_line:
                continue
            commission = self.init_commission(
                start, end, agent, plan_line, base_amount, pattern)
            if self.commission_to_save(commission):
                commissions.append(commission)
        return commissions

    def commission_to_save(self, commission):
        return bool(commission.amount)

    def _get_commission_pattern(self, plan, agent, start, end):
        product = self.product
        pattern = {'agent': agent, 'date_start': start, 'date_end': end}
        if self.invoice.contract:
            pattern['commission_data'] = \
                self.invoice.contract._get_commission_data(agent)
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
                        'commission_start_date': pattern['date_start'],
                        'commission_end_date': pattern['date_end'],
                        'plan': plan,
                        'invoice_line': self,
                        })
            elif self.details[0].fee and not product:
                product = self.details[0].fee.product
        pattern.update({'product': product.id if product else None})
        return pattern

    def init_commission(self, start, end, agent, plan_line,
            base_amount, pattern):
        pool = Pool()
        Date = pool.get('ir.date')
        today = Date.today()
        Commission = pool.get('commission')

        commission = Commission()
        commission.extra_details = {}
        commission.origin = self
        if plan_line.plan.commission_method == 'posting':
            commission.date = today
        commission.start = start
        commission.end = end
        commission.agent = agent
        commission.product = plan_line.plan.commission_product
        commission.commissioned_option = self.details[0].get_option()
        commission.commissioned_contract = self.invoice.contract

        context = self.get_commission_calculation_context(start, end, plan_line,
            base_amount, pattern)
        self.update_commission_from_plan_line(commission, plan_line, context)
        return commission

    def get_commission_calculation_context(self, start, end, plan_line,
            base_amount, pattern):
        amount = base_amount * (
            Decimal((end - start).days + 1
                ) / Decimal(
                (self.coverage_end - self.coverage_start).days + 1))
        context = plan_line.plan.get_context_formula(
            amount, pattern['product'], pattern)
        return context

    def update_commission_from_plan_line(self, commission, plan_line,
            context):
        self.update_commission_amount_and_rate(commission, plan_line, context)

    def update_commission_amount_and_rate(self, commission, plan_line, context):
        commission_amount = self._get_commission_line_amount(plan_line, context)
        commission_amount = commission_amount.quantize(
            Decimal(10) ** -COMMISSION_AMOUNT_DIGITS)
        commission_rate = (commission_amount / context['names']['amount']
            ).quantize(Decimal(10) ** -COMMISSION_RATE_DIGITS)
        commission.amount = commission_amount
        commission.commission_rate = commission_rate
        if commission.amount != 0:
            commission.extra_details.update({
                    'monthly_premium_excl_tax': context['names']['amount'],
                    'rate': commission_rate,
                    'type': 'linear'
                    })

    def _get_commission_line_amount(self, plan_line, context):
        return Decimal(plan_line.get_amount(**context))

    def get_move_lines(self):
        lines = super(InvoiceLine, self).get_move_lines()
        if (not self.account.party_required or not self.invoice.contract or
                not getattr(self.detail, 'fee', None) or
                not self.detail.fee.broker_fee):
            return lines
        if not self.invoice.contract.agent:
            raise ValidationError(gettext(
                    'commission_insurance.msg_no_broker_define_for_broker_fee',
                    contract=self.invoice.contract,
                    fee=self.details.fee.rec_name))
        # Update party to broker for broker fee line
        for line in lines:
            line.party = self.invoice.contract.agent.party
        return lines


class Invoice(metaclass=PoolMeta):
    __name__ = 'account.invoice'
    _agent_commission_method_cache = Cache('agent_commission_method_cache')

    is_insurer_invoice = fields.Function(fields.Boolean('Is insurer commission '
        'invoice'), 'get_is_insurer_invoice',
        searcher='search_is_insurer_invoice')

    @classmethod
    def __setup__(cls):
        super(Invoice, cls).__setup__()
        cls.business_kind.selection += [
            ('broker_invoice', 'Broker Invoice'),
            ('insurer_invoice', 'Insurer Invoice'),
            ]
        for field in ('taxes', 'tax_amount', 'untaxed_amount'):
            getattr(cls, field).states = {
                'invisible': Or(~Eval('tax_amount'),
                    getattr(cls, field).states.get('invisible', False)),
                }
            getattr(cls, field).depends += ['tax_amount']

        cls._check_modify_exclude.append('agent')

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

    @classmethod
    def get_commission_invoice_types(cls):
        return ['insurer_invoice', 'broker_invoice']

    @classmethod
    def get_commission_insurer_invoice_types(cls):
        return ['insurer_invoice']

    def get_is_insurer_invoice(self, name):
        return self.business_kind in self.get_commission_insurer_invoice_types()

    @classmethod
    def search_is_insurer_invoice(cls, name, domain):
        pool = Pool()
        invoice = pool.get('account.invoice').__table__()
        query = invoice.select(invoice.id,
            where=(invoice.business_kind.in_(
                cls.get_commission_insurer_invoice_types())))
        return ['id', 'in', query]

    @classmethod
    def view_attributes(cls):
        is_commission_type = In(Eval('business_kind'),
            cls.get_commission_invoice_types())
        attributes = []
        for path, attr, state in super(Invoice, cls).view_attributes():
            if path == '//group[@id="invoice_lines"]' and attr == 'states':
                state = {
                    'invisible': Or(state['invisible'], is_commission_type),
                    }
            attributes.append((path, attr, state))
        return attributes + [
            ('//group[@id="invoice_lines_commission"]',
                'states', {
                    'invisible': Not(is_commission_type),
                    })
            ]

    def _get_move_line(self, date, amount):
        broker_journal = None
        line = super(Invoice, self)._get_move_line(date, amount)
        configuration = Pool().get('account.configuration').get_singleton()
        if configuration is not None:
            broker_journal = configuration.broker_bank_transfer_journal
        if (getattr(self, 'business_kind', None) == 'broker_invoice' and
                self.type == 'in' and self.total_amount > 0):
            if ((self.business_kind == 'broker_invoice') and
                    (broker_journal is not None)):
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
        Cat = coog_sql.TextCat if backend.name() != 'sqlite' else Concat

        sub_query = invoice_line.select(
            Cat('account.invoice.line,',
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
    def _set_paid_commissions_dates(cls, invoices):
        """For commissions whose plan has the payment_and_accounted
        commission_method, set the commission date as the max between
        today and the commissioned invoice's accounting date"""

        pool = Pool()
        Date = pool.get('ir.date')
        today = Date.today()
        Commission = pool.get('commission')
        InvoiceLine = pool.get('account.invoice.line')
        commission = Commission.__table__()
        invoice = cls.__table__()
        invoice_line = InvoiceLine.__table__()
        cursor = Transaction().connection.cursor()
        method_agents = cls._get_agents_for_method('payment_and_accounted')
        Cat = coog_sql.TextCat if backend.name() != 'sqlite' else Concat
        if not method_agents:
            return super(Invoice, cls)._set_paid_commissions_dates(invoices)

        query_table = commission.join(invoice_line,
                condition=(
                    (commission.origin == Cat(
                        'account.invoice.line,',
                        Cast(invoice_line.id, 'VARCHAR'))
                    ) & commission.agent.in_(method_agents))
            ).join(invoice,
                condition=(
                    (invoice.id == invoice_line.invoice
                        ) & (invoice.id.in_([x.id for x in invoices]))
                    ))

        where_clause = (commission.date == Null)

        date_case = Case(
                    (invoice.accounting_date >= today,
                        invoice.accounting_date),
                    else_=today).as_('commission_date')

        cursor.execute(*query_table.select(commission.id,
                date_case,
                where=where_clause,
                order_by=[date_case]))

        res = list(cursor.fetchall())

        for date, res_lines in groupby(res, key=lambda x: x[1]):
            Commission.write(Commission.browse([x[0] for x in res_lines]),
                {'date': date})

        return super(Invoice, cls)._set_paid_commissions_dates(invoices)

    @classmethod
    def _get_agents_for_method(cls, method):
        Agent = Pool().get('commission.agent')
        cached = cls._agent_commission_method_cache.get(
            method, None)
        if cached is not None:
            return cached
        agents = [x.id for x in Agent.search(
                [('plan.commission_method', '=', method)])]

        cls._agent_commission_method_cache.set(method, agents)
        return agents

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
        for new_com in new_commissions:
            new_com.update_new_commission_after_cancel()
        Commission.save(new_commissions)

    @classmethod
    @ModelView.button
    @Workflow.transition('cancel')
    def cancel(cls, invoices):
        pool = Pool()
        Commission = pool.get('commission')
        MoveLine = pool.get('account.move.line')

        super(Invoice, cls).cancel(invoices)

        commission_invoice_type = cls.get_commission_invoice_types()
        if not any(invoice.business_kind in commission_invoice_type
                for invoice in invoices):
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

    @classmethod
    def modify_invoice_agent(cls, invoices, new_agent):
        assert new_agent
        if invoices:
            cls.write(invoices, {'agent': new_agent.id})

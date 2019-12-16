# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
from dateutil import rrule
from decimal import Decimal

from sql import Cast, Literal, Null
from sql.operators import Concat
from sql.aggregate import Sum, Max, Min
from sql.functions import ToChar

from trytond import backend
from trytond.i18n import gettext
from trytond.config import config
from trytond.pool import PoolMeta, Pool
from trytond.model import Unique, ModelSingleton
from trytond.model.exceptions import AccessError, ValidationError
from trytond.pyson import Eval, Bool, PYSONEncoder
from trytond.wizard import Wizard, StateView, Button, StateTransition
from trytond.wizard import StateAction
from trytond.transaction import Transaction
from trytond.server_context import ServerContext
from trytond.tools import grouped_slice
from trytond.cache import Cache

from trytond.modules.coog_core import (fields, model, export, coog_string,
    coog_date, utils, coog_sql)
from trytond.modules.currency_cog import ModelCurrency
from trytond.modules.product import price_digits

from trytond.modules.coog_core.extra_details import WithExtraDetails

__all__ = [
    'PlanLines',
    'PlanLinesCoverageRelation',
    'Commission',
    'AggregatedCommission',
    'AggregatedCommissionByAgent',
    'Plan',
    'PlanRelation',
    'PlanCalculationDate',
    'Agent',
    'CreateAgents',
    'CreateAgentsParties',
    'CreateAgentsAsk',
    'CreateInvoice',
    'CreateInvoiceAsk',
    'ChangeBroker',
    'SelectNewBroker',
    'FilterCommissions',
    'OpenCommissionsSynthesis',
    'OpenCommissionsSynthesisStart',
    'OpenCommissionsSynthesisShow',
    'OpenCommissionSynthesisYearLine',
    'FilterAggregatedCommissions',
    'CommissionDescriptionConfiguration',
    ]

COMMISSION_AMOUNT_DIGITS = 8
COMMISSION_RATE_DIGITS = 4


class Commission(WithExtraDetails, metaclass=PoolMeta):
    __name__ = 'commission'

    commissioned_contract = fields.Many2One('contract',
        'Commissioned Contract', required=True, ondelete='CASCADE',
        select=True, readonly=True)
    commissioned_option = fields.Many2One('contract.option',
        'Commissioned Option', select=True, ondelete='RESTRICT', readonly=True)
    party = fields.Function(
        fields.Many2One('party.party', 'Party'),
        'get_party', searcher='search_party')
    broker = fields.Function(
        fields.Many2One('distribution.network', 'Broker'),
        'get_broker', searcher='search_broker')
    commission_rate = fields.Numeric('Commission Rate',
        digits=(16, COMMISSION_RATE_DIGITS), readonly=True)
    base_amount = fields.Function(
        fields.Numeric('Base Amount', digits=(16, COMMISSION_AMOUNT_DIGITS)),
        'get_base_amount')
    commissioned_subscriber = fields.Function(
        fields.Many2One('party.party', 'Contract Subscriber'),
        'get_commissioned_subscriber',
        searcher='search_commissioned_subscriber')
    commissioned_covered_element = fields.Function(
        fields.Many2One('contract.covered_element', 'Covered Element'),
        'get_commissioned_covered_element')
    start = fields.Date('Start', readonly=True)
    end = fields.Date('End', readonly=True)
    line_tax_rate = fields.Function(
        fields.Numeric('Line Tax Rate', digits=(16, 2),
            depends=['currency_digits']),
        'get_origin_invoice_line_field')
    line_taxed_amount = fields.Function(
        fields.Numeric('Line Taxed Amount', digits=(16,
                Eval('currency_digits', 2)),
            depends=['currency_digits']),
        'get_origin_invoice_line_field')
    line_tax_amount = fields.Function(
        fields.Numeric('Line Tax Amount', digits=(16,
                Eval('currency_digits', 2)),
            depends=['currency_digits']),
        'get_origin_invoice_line_field')
    line_amount = fields.Function(
        fields.Numeric('Line Amount', digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']),
        'get_origin_invoice_line_field')
    currency_digits = fields.Function(
        fields.Integer('Currency Digits'),
        'get_currency_digits')
    base_tax_amount = fields.Function(
        # No rounding here, it would break the sums
        fields.Numeric('Commissioned amount tax'),
        'getter_base_tax_amount')
    base_full_amount = fields.Function(
        # No rounding here, it would break the sums
        fields.Numeric('Commissioned amount (with taxes)'),
        'getter_base_full_amount')
    calculation_description = fields.Function(
        fields.Char('Calculation Description', help='This field contains a '
            'short functional description on how the commission has been '
            'calculated.'),
        'getter_calculation_description')

    @classmethod
    def __setup__(cls):
        super(Commission, cls).__setup__()
        cls.amount.digits = (16, COMMISSION_AMOUNT_DIGITS)
        cls.invoice_line.select = True
        cls.type_.searcher = 'search_type_'
        cls.agent.select = True
        cls.agent.readonly = True
        cls.date.readonly = True
        cls.agent.readonly = True
        cls.product.readonly = True
        cls.amount.readonly = True
        cls.extra_details.readonly = True

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().connection.cursor()
        commission = TableHandler(cls)

        # Migration from 2.0 : Use real field for contract
        has_contract_column = commission.column_exist('commissioned_contract')

        super(Commission, cls).__register__(module_name)

        if not has_contract_column and config.getboolean('env',
                'testing') is not True:
            pool = Pool()

            # Find contract from contract options
            commission = cls.__table__()
            option = pool.get('contract.option').__table__()
            update_table = commission.join(option,
                condition=(commission.commissioned_option == option.id)
                ).select(commission.id, option.contract,
                where=option.contract != Null)

            commission_up = cls.__table__()
            cursor.execute(*commission_up.update(
                    columns=[commission_up.commissioned_contract],
                    values=[update_table.contract],
                    from_=[update_table],
                    where=(commission_up.id == update_table.id)))

            # Find contract from covered element options
            commission = cls.__table__()
            covered = pool.get('contract.covered_element').__table__()
            option = pool.get('contract.option').__table__()
            update_table = commission.join(option,
                condition=(commission.commissioned_option == option.id)
                ).join(covered, condition=(
                    option.covered_element == covered.id)
                ).select(commission.id, covered.contract, where=(
                    option.covered_element != Null))

            commission_up = cls.__table__()
            cursor.execute(*commission_up.update(
                    columns=[commission_up.commissioned_contract],
                    values=[update_table.contract],
                    from_=[update_table],
                    where=(commission_up.id == update_table.id)
                    & (commission_up.commissioned_contract == Null)))

            # Find contract from invoice lines
            commission = cls.__table__()
            invoice_line = pool.get('account.invoice.line').__table__()
            contract_invoice = pool.get('contract.invoice').__table__()
            update_table = commission.join(invoice_line,
                condition=(Concat('account.invoice.line,',
                        Cast(invoice_line.id, 'VARCHAR')) == commission.origin)
                ).join(contract_invoice, condition=(
                    invoice_line.invoice == contract_invoice.invoice)
                ).select(commission.id, contract_invoice.contract)
            commission_up = cls.__table__()
            cursor.execute(*commission_up.update(
                    columns=[commission_up.commissioned_contract],
                    values=[update_table.contract],
                    from_=[update_table],
                    where=(commission_up.id == update_table.id)
                    & (commission_up.commissioned_contract == Null)))

    @classmethod
    def delete(cls, instances):
        for commission in instances:
            if commission.invoice_line:
                raise AccessError(gettext(
                        'commission_insurance'))
        super(Commission, cls).delete(instances)

    @classmethod
    def write(cls, *args):
        # Bypass to allow reset of 'invoice_line' field on broker invoice
        # deletion
        override = ServerContext().get('allow_modify_commissions', False)
        with Transaction().set_context(_check_access=not override and
                Transaction().context.get('_check_access', False)):
            super(Commission, cls).write(*args)

    def get_origin_invoice_line_field(self, name):
        if getattr(self.origin, '__name__', '') != 'account.invoice.line':
            return
        return abs(getattr(self.origin, name[5:], None) or 0)

    def get_currency_digits(self, name):
        return self.currency.digits if self.currency else 2

    def get_base_amount(self, name):
        if self.amount and self.commission_rate:
            return self.amount / self.commission_rate
        return Decimal(0)

    def getter_base_tax_amount(self, name):
        # We cannot directly use the line_tax_amount field because sometimes
        # the periods do not match (for instance when there is a commission
        # rate change in the middle of the invoiced period.
        # We could use start / end vs line.start / line.end to compute a
        # prorata, but since we already have the ratio in line_amount /
        # base_amount, so we can reuse that.
        if not self.line_amount:
            return Decimal(0)
        return ((self.base_amount / self.line_amount) *
            self.line_tax_amount)

    def getter_base_full_amount(self, name):
        return self.base_amount + self.base_tax_amount

    def get_commissioned_subscriber(self, name):
        return self.commissioned_contract.subscriber.id

    def get_commissioned_covered_element(self, name):
        if (self.commissioned_option and
                self.commissioned_option.covered_element):
            return self.commissioned_option.covered_element.id

    @classmethod
    def search_commissioned_subscriber(cls, name, clause):
        return [('commissioned_contract.subscriber',) + tuple(clause[1:])]

    def get_party(self, name):
        return self.agent.party.id if self.agent else None

    def get_broker(self, name):
        return (self.agent.party.network[0].id
            if self.agent and self.agent.party.is_broker else None)

    @classmethod
    def _get_invoice(cls, key):
        Invoice = Pool().get('account.invoice')

        party = key['party']
        payment_term = key['payment_term']
        return Invoice(
            company=key['company'],
            type=key['type'],
            journal=cls.get_journal(),
            party=party,
            invoice_address=party.address_get(type='invoice'),
            currency=key['currency'],
            account=key['account'],
            payment_term=payment_term,
            business_kind='broker_invoice',
            )

    def _group_to_invoice_key(self):
        direction = {
            'in': 'out',
            'out': 'in',
            }.get(self.type_)
        return (('party', self.agent.party),
            ('type', direction),
            ('company', self.agent.company),
            ('currency', self.agent.currency),
            ('account', self.agent.account),
            ('payment_term', self.agent.get_payment_term_from_party(
                    self.type_)),
            )

    def _group_to_invoice_line_key(self):
        return super(Commission, self)._group_to_invoice_line_key() + (
            ('agent', self.agent),)

    @classmethod
    @model.CoogView.button
    def invoice(cls, commissions):
        pool = Pool()
        Event = pool.get('event')
        Fee = pool.get('account.fee')
        super(Commission, cls).invoice(commissions)
        invoices = list(set([c.invoice_line.invoice for c in commissions]))
        Fee.add_broker_fees_to_invoice(invoices)
        Event.notify_events(invoices, 'commission_invoice_generated')
        return invoices

    @classmethod
    def cancel(cls, commissions):
        # Force date for commissions which are going to be canceled, so
        # they are properly fetched in broker invoice generation
        to_write = []
        for commission in commissions:
            if not commission.date:
                to_write.append(commission)
        if to_write:
            cls.write(to_write, {'date': utils.today()})
        return super(Commission, cls).cancel(commissions)

    def update_new_commission_after_cancel(self):
        self.amount *= -1

    def update_cancel_copy(self):
        super(Commission, self).update_cancel_copy()
        self.date = utils.today()
        self.update_agent_from_contract()

    def update_agent_from_contract(self):
        if self.agent.type_ != 'agent':
            return
        if not self.commissioned_contract:
            return
        new_agent = self.commissioned_contract.agent
        if new_agent != self.agent:
            self.agent = self.commissioned_contract.agent

    @classmethod
    def _get_invoice_line(cls, key, invoice, commissions):
        invoice_line = super(Commission, cls)._get_invoice_line(key, invoice,
            commissions)
        invoice_line.description = key['agent'].rec_name
        return invoice_line

    @classmethod
    def search_type_(cls, name, clause):
        clause[2] = {'out': 'agent', 'in': 'principal'}.get(clause[2], '')
        return [('agent.type_',) + tuple(clause[1:])],

    @classmethod
    def search_party(cls, name, clause):
        return [('agent.party',) + tuple(clause[1:])],

    @classmethod
    def search_broker(cls, name, clause):
        return ['AND',
            [('agent.party.network',) + tuple(clause[1:])],
            [('agent.party.network.is_broker', '=', True)]]

    @classmethod
    def modify_agent(cls, commissions, new_agent):
        assert new_agent
        to_update, to_cancel = [], []
        for commission in commissions:
            if not commission.date:
                to_update.append(commission)
            else:
                to_cancel.append(commission)
        if to_update:
            cls.write(to_update, {'agent': new_agent.id})
        if to_cancel:
            to_save = []
            for line in cls.copy(to_cancel):
                line.update_new_commission_after_cancel()
                to_save.append(line)
            for line in cls.copy(to_cancel):
                line.agent = new_agent
                to_save.append(line)
            cls.save(to_save)

    def getter_calculation_description(self, name):
        description = ''
        details = self.extra_details or {}
        if details.get('type', '') == 'linear':
            commission_title = ''
            desc_configuration = Pool().get(
                'commission.description.configuration').get_singleton()
            if (desc_configuration
                    and desc_configuration.linear_commission_title):
                commission_title = desc_configuration.linear_commission_title
            description += '%s\n%s = %s * %s' % (
                commission_title,
                str(self.amount) if self.amount is not None else '',
                str(self.base_amount),
                str(details.get('rate', 0)))
        return description


class AggregatedCommission(model.CoogSQL, model.CoogView):
    'Commission Aggregated'

    __name__ = 'commission.aggregated'

    agent = fields.Many2One('commission.agent', 'Agent', readonly=True)
    party = fields.Many2One('party.party', 'Party', readonly=True)
    invoice = fields.Many2One('account.invoice', 'Invoice', readonly=True)
    date = fields.Date('Date', readonly=True)
    contract = fields.Many2One('contract', 'Contract', readonly=True)
    commissioned_option = fields.Many2One('contract.option',
        'Commissioned Option', readonly=True, states={'invisible': True})
    broker = fields.Function(
        fields.Many2One('distribution.network', 'Broker', readonly=True),
        'get_broker', searcher='search_broker')
    subscriber = fields.Function(
        fields.Many2One('party.party', 'Contract Subscriber', readonly=True),
        'get_subscriber',
        searcher='search_commissioned_subscriber')
    start = fields.Date('Start Date', readonly=True)
    end = fields.Date('End Date', readonly=True)
    currency_digits = fields.Function(
        fields.Integer('Currency Digits', states={'invisible': True}),
        'get_currency_digits')
    total_commission = fields.Numeric('Total', readonly=True,
        digits=(16, Eval('currency_digits', 2)), depends=['currency_digits'])
    invoice_state = fields.Function(
        fields.Selection([
                ('draft', 'Draft'),
                ('validated', 'Validated'),
                ('posted', 'Posted'),
                ('paid', 'Paid'),
                ('cancel', 'Canceled'),
                ], 'Client Invoice State', readonly=True),
        'get_invoice_state')

    def get_currency_digits(self, name):
        return self.invoice.currency_digits if self.invoice else 2

    @classmethod
    def __setup__(cls):
        super(AggregatedCommission, cls).__setup__()
        cls._order = [('agent', 'DESC'), ('start', 'ASC'),
            ('total_commission', 'DESC')]

    @classmethod
    def read(cls, ids, fields_names=None):
        if 'origins' not in Transaction().context and ids:
            cursor = Transaction().connection.cursor()
            commission = Pool().get('commission').__table__()
            cursor.execute(*commission.select(commission.origin,
                    where=commission.id.in_(ids),
                    group_by=[commission.origin]))
            origins = [x[0] for x in cursor.fetchall()]
            with Transaction().set_context(origins=origins):
                return super(AggregatedCommission, cls).read(ids,
                    fields_names)
        return super(AggregatedCommission, cls).read(ids, fields_names)

    def get_broker(self, name):
        return (self.agent.party.network[0].id
            if self.agent and self.agent.party.is_broker else None)

    @classmethod
    def search_broker(cls, name, clause):
        return ['AND',
            [('agent.party.network',) + tuple(clause[1:])],
            [('agent.party.network.is_broker', '=', True)]]

    def get_subscriber(self, name):
        if self.contract:
            return self.contract.subscriber.id

    @classmethod
    def search_commissioned_subscriber(cls, name, clause):
        return [('contract.subscriber',) + tuple(clause[1:])]

    def get_invoice_state(self, name=None):
        return self.invoice.state if self.invoice else None

    @classmethod
    def get_tables(cls):
        pool = Pool()
        commission = pool.get('commission').__table__()
        agent = pool.get('commission.agent').__table__()
        invoice_line = pool.get('account.invoice.line').__table__()
        return {
            'commission': commission,
            'account.invoice.line': invoice_line,
            'commission.agent': agent,
            }

    @classmethod
    def get_query_table(cls, tables):
        commission = tables['commission']
        agent = tables['commission.agent']
        invoice_line = tables['account.invoice.line']
        Cat = coog_sql.TextCat if backend.name() != 'sqlite' else Concat

        commission_agent = commission.join(agent,
            condition=commission.agent == agent.id)

        return commission_agent.join(invoice_line, type_='LEFT OUTER',
                condition=(commission.origin == Cat(
                    'account.invoice.line,', Cast(invoice_line.id, 'VARCHAR')))
                )

    @classmethod
    def get_where_clause(cls, tables):
        origins = Transaction().context.get('origins', None)
        commission = tables['commission']
        if origins:
            return commission.origin.in_(origins)
        return None

    @classmethod
    def get_fields_to_select(cls, tables):
        commission = tables['commission']
        agent = tables['commission.agent']
        invoice_line = tables['account.invoice.line']

        return (
            Max(commission.id).as_('id'),
            agent.party.as_('party'),
            invoice_line.invoice.as_('invoice'),
            Literal(0).as_('create_uid'),
            Min(commission.create_date).as_('create_date'),
            Literal(0).as_('write_uid'),
            Max(commission.write_date).as_('write_date'),
            commission.agent.as_('agent'),
            Max(commission.commissioned_contract).as_('contract'),
            Max(commission.commissioned_option).as_('commissioned_option'),
            Min(commission.start).as_('start'),
            Max(commission.end).as_('end'),
            Max(commission.date).as_('date'),
            Sum(commission.amount).as_('total_commission'))

    @classmethod
    def get_group_by(cls, tables):
        commission = tables['commission']
        agent = tables['commission.agent']
        invoice_line = tables['account.invoice.line']
        return [commission.agent, invoice_line.invoice, agent.party]

    @staticmethod
    def table_query():
        klass = Pool().get('commission.aggregated')
        tables = klass.get_tables()
        query_table = klass.get_query_table(tables)

        return query_table.select(*klass.get_fields_to_select(tables),
            where=klass.get_where_clause(tables),
            group_by=klass.get_group_by(tables))


class Plan(model.ConfigurationMixin, model.CoogView, model.TaggedMixin):
    __name__ = 'commission.plan'
    _func_key = 'code'

    code = fields.Char('Code', required=True)
    active = fields.Boolean('Active')
    type_ = fields.Selection([
            ('agent', 'Broker'),
            ('principal', 'Insurer'),
            ], 'Type', required=True)
    insurer_plan = fields.One2One('commission_plan-commission_plan',
        'from_', 'to', 'Insurer Plan',
        states={'invisible': Eval('type_') != 'agent'},
        domain=[('type_', '=', 'principal')],
        depends=['type_'])
    computation_dates = fields.One2Many('commission.plan.date', 'plan',
        'Computation Dates', delete_missing=True)
    commissioned_products = fields.Function(
        fields.Many2Many('offered.product', None, None,
            'Commissioned Products'),
        'get_commissioned_products', searcher='search_commissioned_products')
    commissioned_products_name = fields.Function(
        fields.Char('Commissioned Products'),
        'get_commissioned_products_name',
        searcher='search_commissioned_products')

    @classmethod
    def __setup__(cls):
        super(Plan, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('code_uniq', Unique(t, t.code), 'The code must be unique!'),
            ]
        cls.commission_method.selection.append(('payment_and_accounted',
                'On Payment And Accounted'))
        cls.commission_method.help = cls.commission_method.help + \
            '. If "On Payment And Accounted"' \
            ' is selected, a commission is due after its invoice\'s' \
            ' accounting date, if the invoice is paid.'
        cls._function_auto_cache_fields.append('commissioned_products')

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        Contract = pool.get('contract')
        Invoice = pool.get('account.invoice')
        Invoice._agent_commission_method_cache.clear()
        Contract.insurer_agent_cache.clear()
        return super(Plan, cls).create(vlist)

    @classmethod
    def write(cls, *args):
        pool = Pool()
        Contract = pool.get('contract')
        Invoice = pool.get('account.invoice')
        Invoice._agent_commission_method_cache.clear()
        Contract.insurer_agent_cache.clear()
        super(Plan, cls).write(*args)

    @classmethod
    def _export_light(cls):
        return super(Plan, cls)._export_light() | {'commission_product'}

    @classmethod
    def copy(cls, commissions, default=None):
        if default is None:
            default = {}
        default.setdefault('code', 'temp_for_copy')
        clones = super(Plan, cls).copy(commissions, default=default)
        for clone, original in zip(clones, commissions):
            clone.code = original.code + '_1'
            clone.save()
        return clones

    @staticmethod
    def default_commission_method():
        return 'payment_and_accounted'

    @staticmethod
    def default_type_():
        return 'agent'

    @staticmethod
    def default_lines():
        return [{}]

    @staticmethod
    def default_active():
        return True

    def get_context_formula(self, amount, product, pattern=None):
        context = super(Plan, self).get_context_formula(amount, product)
        context['names']['nb_years'] = (pattern or {}).get('nb_years', 0)
        context['names']['commission_end_date'] = (pattern or {}).get(
            'commission_end_date', 0)
        context['names']['commission_start_date'] = (pattern or {}).get(
            'commission_start_date', 0)
        context['names']['invoice_line'] = (pattern or {}).get('invoice_line',
            None)
        return context

    def get_matching_line(self, pattern=None):
        if pattern is None:
            pattern = {}
        for line in self.lines:
            if line.match(pattern):
                return line

    @classmethod
    def is_master_object(cls):
        return True

    @fields.depends('code', 'name')
    def on_change_with_code(self):
        if self.code:
            return self.code
        return coog_string.slugify(self.name)

    def get_commissioned_products(self, name):
        products = []
        for line in self.lines:
            for option in line.options:
                products.extend([product.id for product in option.products])
        return list(set(products))

    def get_commissioned_products_name(self, name):
        return ', '.join([x.rec_name for x in self.commissioned_products])

    @classmethod
    def search_commissioned_products(cls, name, clause):
        return [('lines.options.products',) + tuple(clause[1:])]

    def get_commission_periods(self, invoice_line):
        periods = []
        all_dates = self.get_commission_dates(invoice_line)
        if len(all_dates) == 1:
            return [(all_dates[0], all_dates[0])]
        for idx, date in enumerate(all_dates[:-1]):
            if idx == len(all_dates) - 2:
                # Last date must be inside
                periods.append((date, all_dates[-1]))
            else:
                periods.append((date,
                        coog_date.add_day(all_dates[idx + 1], -1)))
        return periods

    def get_commission_dates(self, invoice_line):
        all_dates = {invoice_line.coverage_start, invoice_line.coverage_end}
        for date_line in self.computation_dates:
            all_dates |= date_line.get_dates(invoice_line)
        return sorted(list(all_dates))


class PlanLines(model.ConfigurationMixin, model.CoogView):
    __name__ = 'commission.plan.line'

    options = fields.Many2Many(
        'commission.plan.lines-offered.option.description', 'plan_line',
        'option', 'Options')
    options_extract = fields.Function(fields.Text('Options'),
        'get_options_extract')
    _get_matching_cache = Cache('get_matching_cache')
    formula_description = fields.Function(fields.Text('Formula'),
        'get_formula_description')

    @classmethod
    def create(cls, vlist):
        cls._get_matching_cache.clear()
        return super(PlanLines, cls).create(vlist)

    @classmethod
    def write(cls, *args):
        super(PlanLines, cls).write(*args)
        cls._get_matching_cache.clear()

    @classmethod
    def delete(cls, plan_lines):
        super(PlanLines, cls).delete(plan_lines)
        cls._get_matching_cache.clear()

    def get_cache_key(self, coverage_id, pattern):
        return (self.id, coverage_id)

    def get_option_ids(self, pattern):
        return {o.id for o in self.options}

    def match(self, pattern):
        if 'coverage' not in pattern:
            if 'product' in pattern and self.product:
                return pattern['product'] == self.product.id
            else:
                return False
        coverage_id = pattern['coverage'].id
        key = self.get_cache_key(coverage_id, pattern)
        option_ids = self._get_matching_cache.get(key, -1)
        if option_ids != -1:
            return coverage_id in option_ids
        option_ids = self.get_option_ids(pattern)
        self._get_matching_cache.set(key, option_ids)
        return coverage_id in option_ids

    def get_options_extract(self, name):
        products = []
        for o in self.options:
            products += o.products
        lines = []
        for product in list(set(products)):
            lines.append('%s (%s)' % (
                    product.rec_name,
                    ', '.join([option.name for option in product.coverages
                            if option in self.options])))
        return ' \n'.join(lines)

    def get_formula_description(self, name):
        return self.formula if self.formula else ''

    @classmethod
    def _export_light(cls):
        return (super(PlanLines, cls)._export_light() | set(['options']))

    def get_func_key(self, name):
        return self.options_extract


class PlanLinesCoverageRelation(model.ConfigurationMixin, model.CoogView):
    'Commission Plan Line - Offered Option Description'

    __name__ = 'commission.plan.lines-offered.option.description'

    plan_line = fields.Many2One('commission.plan.line', 'Plan Line',
        ondelete='CASCADE')
    option = fields.Many2One('offered.option.description', 'Option',
        ondelete='RESTRICT')


class PlanRelation(model.ConfigurationMixin, model.CoogView):
    'Commission Plan - Commission Plan'

    __name__ = 'commission_plan-commission_plan'

    from_ = fields.Many2One('commission.plan', 'Plan', ondelete='CASCADE')
    to = fields.Many2One('commission.plan', 'Plan', ondelete='RESTRICT')


class PlanCalculationDate(model.ConfigurationMixin, model.CoogView):
    'Plan Calculation Date'

    __name__ = 'commission.plan.date'

    plan = fields.Many2One('commission.plan', 'Plan', ondelete='CASCADE',
        required=True, select=True)
    type_ = fields.Selection([
            ('absolute', 'Absolute Date'),
            ('relative', 'Relative Date'),
            ], 'Rule Type')
    frequency = fields.Selection([
            ('', ''),
            ('yearly', 'Yearly'),
            ('monthly', 'Monthly'),
            ], 'Frequency', states={
            'invisible': Eval('type_') != 'absolute',
            'required': Eval('type_') == 'absolute',
            }, depends=['type_'])
    first_match_only = fields.Boolean('First Match Only',
        help='If True, only the first matching date will be considered.')
    reference_date = fields.Selection([
            ('contract_start', 'Contract Start'),
            ('contract_signature', 'Contract Signature'),
            ('option_start', 'Option Start'),
            ], 'Reference Date')
    year = fields.Selection([('', '')] + [
            (str(x), str(x)) for x in range(10)], 'Year', states={
            'invisible': Eval('type_') != 'relative',
            }, depends=['type_'])
    month = fields.Selection([('', '')] + [
            (str(x), str(x)) for x in range(12)], 'Month')
    day = fields.Selection([('', '')] + [
            (str(x), str(x)) for x in range(31)], 'Day')

    @classmethod
    def validate(cls, dates):
        for date in dates:
            if date.type_ == 'relative':
                if not date.day and not date.month and not date.year:
                    raise ValidationError(gettext(
                            'commission_insurance.msg_need_date_field_set'))
            elif date.type_ == 'absolute':
                try:
                    date = datetime.date(2000, int(date.month), int(date.day))
                except ValueError:
                    raise ValidationError(gettext(
                            'commission_insurance'
                            '.msg_invalid_month_day_combination',
                            month=date.month, day=date.day))

    @classmethod
    def default_first_match_only(cls):
        return True

    @classmethod
    def default_reference_date(cls):
        return 'contract_start'

    @classmethod
    def default_type_(cls):
        return 'relative'

    @fields.depends('frequency', 'day', 'month', 'year', 'type_')
    def on_change_type_(self):
        if self.type_ == 'absolute':
            self.frequency = ''
        elif self.type_ == 'relative':
            self.frequency = 'yearly'

    def get_dates(self, invoice_line):
        base_date = self.get_reference_date(invoice_line)
        if not base_date:
            return set()
        if self.type_ == 'absolute':
            values = [x.date() for x in rrule.rrule(self.get_rrule_frequency(),
                    bymonth=int(self.month), bymonthday=int(self.day),
                    dtstart=base_date, until=invoice_line.coverage_end)]
        elif self.type_ == 'relative':
            values = []
            date = base_date
            while date < invoice_line.coverage_end:
                for fname in ('year', 'month', 'day'):
                    value = getattr(self, fname, None)
                    if not value:
                        continue
                    date = getattr(coog_date, 'add_%s' % fname)(date,
                        int(value))
                values.append(date)
        if not values:
            # invoice_line in the past following a start_date modification for
            # instance
            return set()
        if self.first_match_only:
            values = [values[0]]
        return {x for x in values if x > invoice_line.coverage_start and
            x < invoice_line.coverage_end}

    def get_rrule_frequency(self):
        if self.frequency == 'yearly':
            return rrule.YEARLY
        if self.frequency == 'monthly':
            return rrule.MONTHLY

    def get_reference_date(self, invoice_line):
        if self.reference_date == 'contract_start':
            return invoice_line.invoice.contract.initial_start_date
        if self.reference_date == 'contract_signature':
            return invoice_line.invoice.contract.signature_date
        if self.reference_date == 'option_start':
            return invoice_line.details[0].get_option().initial_start_date


class Agent(export.ExportImportMixin, model.FunctionalErrorMixIn):
    __name__ = 'commission.agent'
    _func_key = 'code'

    code = fields.Char('Code', required=True)
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    active = fields.Function(fields.Boolean('Active'), 'get_active',
        searcher='search_active')
    agent_payment_term = fields.Many2One(
        'account.invoice.payment_term', 'Commission Agent Payment Term',
        ondelete='RESTRICT', help='If defined, this payment term has priority '
        'over the party\'s one and the global configuration')
    commissioned_products = fields.Function(
        fields.Many2Many('offered.product', None, None,
            'Commissioned Products'),
        'get_commissioned_products', searcher='search_commissioned_products')
    commissioned_products_name = fields.Function(
        fields.Char('Commissioned Products'),
        'get_commissioned_products_name',
        searcher='search_commissioned_products')
    icon = fields.Function(fields.Char('Icon'), 'on_change_with_icon')

    @classmethod
    def __register__(cls, module_name):
        # Migration from 1.14 : add code
        TableHandler = backend.get('TableHandler')
        table_handler = TableHandler(cls)
        do_migrate = not table_handler.column_exist('code')
        super(Agent, cls).__register__(module_name)
        if not do_migrate:
            return
        for agent_slice in grouped_slice(cls.search([])):
            agents = []
            for agent in agent_slice:
                agent.code = '%s_%s' % (agent.id, agent.on_change_with_code())
                agents.append(agent)
            cls.save(agents)

    @classmethod
    def __setup__(cls):
        super(Agent, cls).__setup__()
        cls.plan.domain = [('type_', '=', Eval('type_'))]
        cls.plan.depends = ['type_']
        cls.plan.required = True
        cls.plan.select = True
        cls.party.select = True
        cls.party.domain = ['OR', ('is_broker', '=', True),
                ('is_insurer', '=', True),
                ]
        t = cls.__table__()
        cls._sql_constraints += [
            ('code_unique', Unique(t, t.code), 'The code must be unique')]

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        Contract = pool.get('contract')
        Invoice = pool.get('account.invoice')
        Invoice._agent_commission_method_cache.clear()
        Contract.insurer_agent_cache.clear()
        return super(Agent, cls).create(vlist)

    @classmethod
    def write(cls, *args):
        pool = Pool()
        Contract = pool.get('contract')
        Invoice = pool.get('account.invoice')
        Invoice._agent_commission_method_cache.clear()
        Contract.insurer_agent_cache.clear()
        super(Agent, cls).write(*args)

    @classmethod
    def is_master_object(cls):
        return True

    @classmethod
    def _export_light(cls):
        return (super(Agent, cls)._export_light() |
            set(['company', 'currency', 'plan']))

    @fields.depends('type_')
    def on_change_with_icon(self, name=None):
        return {
            'agent': 'cash-out',
            'principal': 'cash-in',
            }[self.type_] if self.type_ else ''

    @fields.depends('code', 'party', 'plan')
    def on_change_with_code(self):
        if self.code or not self.party or not self.plan:
            return self.code
        else:
            return coog_string.slugify(self.party.code + '_' + self.plan.code)

    def get_payment_term_from_party(self, type_):
        AccountConfiguration = Pool().get('account.configuration')
        if self.agent_payment_term:
            return self.agent_payment_term
        if type_.startswith('out'):
            payment_term = self.party.customer_payment_term
        else:
            payment_term = self.party.supplier_payment_term
        if not payment_term:
            conf = AccountConfiguration(1)
            payment_term = conf.commission_invoice_payment_term
        return payment_term

    def get_rec_name(self, name):
        return self.plan.rec_name

    def get_commissioned_products(self, name):
        return [p.id for p in self.plan.commissioned_products
            ] if self.plan else []

    def get_commissioned_products_name(self, name):
        return ', '.join([x.rec_name for x in self.commissioned_products])

    def get_active(self, name):
        return not self.plan.active

    @classmethod
    def search_commissioned_products(cls, name, clause):
        return [('plan.commissioned_products',) + tuple(clause[1:])]

    @classmethod
    def search_active(cls, name, clause):
        reverse = {
            '=': '!=',
            '!=': '=',
            }
        if clause[1] in reverse:
            if clause[2]:
                return [('plan.active', clause[1], True)]
            else:
                return [('plan.active', reverse[clause[1]], True)]
        else:
            return []

    @classmethod
    def find_matches(cls, agents, target_broker):
        source_keys = {agent: agent.get_hash() for agent in agents}
        target_keys = {agent.get_hash(): agent
            for agent in target_broker.agents}
        matches = {}
        for source_agent, source_key in source_keys.items():
            matches[source_agent] = target_keys.get(source_key, None)
        return matches

    @classmethod
    def format_hash(cls, hash_dict):
        return coog_string.translate_label(cls, 'plan') + ' : ' + \
            hash_dict['plan'].rec_name

    def get_hash(self):
        return (('plan', self.plan),)

    def copy_to_broker(self, target_broker):
        return self.copy([self], default={'party': target_broker.id})[0]

    @classmethod
    def find_agents(cls, **kwargs):
        '''
            Find agents matching a pattern
        '''
        return cls.search(cls._find_agents_domain(**kwargs))

    @classmethod
    def _find_agents_domain(cls, type_=None, products=None, brokers=None,
            dist_network=None, **kwargs):
        domain = []
        if type_:
            domain.append(('type_', '=', type_))
        if products:
            domain.append(
                ('plan.commissioned_products', 'in', [x.id for x in products]))
        if dist_network:
            brokers = [x.party for x in dist_network.parent_brokers]
        if brokers:
            domain.append(
                ('party', 'in', [x.id for x in brokers]))
        return domain


class CreateAgents(Wizard):
    'Create Agents'

    __name__ = 'commission.create_agents'

    start_state = 'parties'
    parties = StateView('commission.create_agents.parties',
        'commission_insurance.commission_create_agents_parties_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Next', 'create_brokers', 'tryton-go-next',
                default=True),
            ])
    create_brokers = StateTransition()
    ask = StateView('commission.create_agents.ask',
        'commission_insurance.commission_create_agents_ask_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('OK', 'create_', 'tryton-ok', default=True),
            ])
    create_ = StateAction('commission.act_agent_form')

    def transition_create_brokers(self):
        pool = Pool()
        Party = pool.get('party.party')
        PaymentTerm = pool.get('account.invoice.payment_term')
        payment_terms = PaymentTerm.search([])
        if self.parties.parties:
            Party.write(list(self.parties.parties), {
                    'account_payable': self.parties.account_payable_used.id,
                    'supplier_payment_term': payment_terms[0].id,
                    })

        Network = pool.get('distribution.network')
        networks = []
        Address = pool.get('party.address')
        adresses_to_create = []
        adresses_to_write = []
        for party in self.parties.parties:
            address = party.address_get('invoice')
            if not address:
                adresses_to_create.append({'party': party.id, 'invoice': True})
            elif not address.invoice:
                adresses_to_write.append(address)
            if party.network:
                continue
            networks.append({'party': party.id})

        if networks:
            Network.create(networks)
        if adresses_to_create:
            Address.create(adresses_to_create)
        if adresses_to_write:
            Address.write(adresses_to_write, {'invoice': True})
        return 'ask'

    def new_agent(self, party, plan):
        return {
            'party': party.id,
            'plan': plan.id,
            'company': self.parties.company.id,
            'currency': self.parties.company.currency.id,
            'type_': 'agent',
            }

    def agent_update_values(self):
        return {}

    def do_create_(self, action):
        pool = Pool()
        Agent = pool.get('commission.agent')
        existing_agents = {}
        agents_to_create = []
        agents_to_update = []
        agents = []
        for party_slice in grouped_slice([x.party for x in self.ask.brokers]):
            for agent in Agent.search([
                    ('party', 'in', [x.id for x in party_slice]),
                    ('plan', 'in', [x.id for x in self.ask.plans]),
                    ('company', '=', self.parties.company),
                    ('currency', '=', self.parties.company.currency),
                    ('type_', '=', 'agent'),
                    ]):
                existing_agents[(agent.party.id, agent.plan.id)] = agent
        for party in [x.party for x in self.ask.brokers]:
            for plan in self.ask.plans:
                agent = existing_agents.get((party.id, plan.id), None)
                if agent:
                    agents_to_update.append(agent)
                else:
                    agents_to_create.append(self.new_agent(party, plan))
        if agents_to_create:
            agents += [x.id for x in Agent.create(agents_to_create)]

        vals = self.agent_update_values()
        if vals and agents_to_update:
            Agent.write(agents_to_update, vals)
            agents += [x.id for x in agents_to_update]
        encoder = PYSONEncoder()
        action['pyson_domain'] = encoder.encode([('id', 'in', agents)])
        action['pyson_search_value'] = encoder.encode([])
        return action, {}

    def default_ask(self, name):
        return {
            'brokers': [x.network[0].id for x in self.parties.parties],
            }


class CreateAgentsParties(model.CoogView):
    'Create Agents'

    __name__ = 'commission.create_agents.parties'

    company = fields.Many2One('company.company', 'Company', required=True)
    parties = fields.Many2Many('party.party', None, None, 'Parties',
        domain=[
            ('is_person', '=', False),
            ('is_bank', '=', False),
            ('is_insurer', '=', False),
            ])
    account_payable = fields.Many2One('account.account', 'Account Payable',
        domain=[
            ('kind', '=', 'payable'),
            ('company', '=', Eval('company')),
            ],
        states={'required': Bool(Eval('parties'))},
        depends=['company', 'parties'])

    @staticmethod
    def default_company():
        return Transaction().context.get('company')


class CreateAgentsAsk(model.CoogView):
    'Create Agents'

    __name__ = 'commission.create_agents.ask'

    company = fields.Many2One('company.company', 'Company', required=True)
    brokers = fields.Many2Many('distribution.network', None, None, 'Brokers',
        domain=[('is_broker', '=', True)], required=True)
    plans = fields.Many2Many('commission.plan', None, None, 'Plans',
        domain=[('type_', '=', 'agent')], required=True)

    @staticmethod
    def default_company():
        return Transaction().context.get('company')


class CreateInvoice(metaclass=PoolMeta):
    __name__ = 'commission.create_invoice'

    def do_create_(self, action):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        Commission = pool.get('commission')

        agent_type = None
        if self.ask.type_ == 'in':
            agent_type = 'principal'
        elif self.ask.type_ == 'out':
            agent_type = 'agent'

        broker_ids = [x.id for x in self.ask.brokers] if not \
            self.ask.all_brokers else None

        commissions = self.fetch_commmissions_to_invoice(
            self.ask.from_, self.ask.to, agent_type,
            broker_ids)
        invoices = Commission.invoice(commissions)
        Invoice.write(invoices, {'invoice_date': self.ask.to})
        if self.ask.post_invoices:
            Invoice.post(invoices)
        encoder = PYSONEncoder()
        action['pyson_domain'] = encoder.encode(
               [('id', 'in', [i.id for i in invoices])])
        action['pyson_search_value'] = encoder.encode([])
        return action, {}

    @classmethod
    def _get_models_for_query(cls):
        return ['commission.agent', 'commission']

    @classmethod
    def _get_tables(cls):
        pool = Pool()
        return {model_: pool.get(model_).__table__()
            for model_ in cls._get_models_for_query()}

    @classmethod
    def _get_commission_insurance_where_clause(cls, tables):
        commission = tables['commission']
        return ((commission.invoice_line == Null) & (
                commission.date != Null))

    @classmethod
    def fetch_commmissions_to_invoice(cls, from_=None, to=None, agent_type=None,
            agent_party_ids=None):
        pool = Pool()
        tables = cls._get_tables()
        agent = tables['commission.agent']
        commission = tables['commission']

        query_table = agent.join(commission, condition=(
                commission.agent == agent.id))

        where_clause = cls._get_commission_insurance_where_clause(tables)
        if agent_type:
            where_clause &= (agent.type_ == agent_type)
        if from_:
            where_clause &= (commission.date >= from_)
        if to:
            where_clause &= (commission.date <= to)
        if agent_party_ids:
            where_clause &= (agent.party.in_(agent_party_ids))

        cursor = Transaction().connection.cursor()
        cursor.execute(*query_table.select(commission.id,
                where=where_clause,
                order_by=[commission.agent.desc, commission.date.desc]))

        return pool.get('commission').browse([x for x, in cursor.fetchall()])


class CreateInvoiceAsk(metaclass=PoolMeta):
    __name__ = 'commission.create_invoice.ask'

    post_invoices = fields.Boolean('Post Invoices')
    all_brokers = fields.Boolean('All brokers')
    brokers = fields.Many2Many('party.party', None, None, 'Brokers',
        states={
            'required': ~Eval('all_brokers'),
            'invisible': Bool(Eval('all_brokers')),
            },
        depends=['all_brokers'],
        domain=[('is_broker', '=', True)])

    @classmethod
    def __setup__(cls):
        super(CreateInvoiceAsk, cls).__setup__()
        cls.type_.states = {'invisible': True}
        cls.to.states = {'required': Bool(Eval('post_invoices'))}
        cls.to.depends += ['post_invoices']

    @staticmethod
    def default_type_():
        return 'out'

    @staticmethod
    def default_all_brokers():
        return True


class OpenCommissionsSynthesis(Wizard):
    'Open Commissions Synthesis'

    __name__ = 'commission.synthesis'

    start_state = 'select_account'
    select_account = StateTransition()
    start = StateView('commission.synthesis.start',
        'commission_insurance.synthesis_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Show', 'show', 'tryton-go-next', default=True),
            ])
    show = StateView('commission.synthesis.show',
        'commission_insurance.synthesis_show_view_form', [
            Button('Ok', 'end', 'tryton-ok', default=True),
            ])

    def default_start(self, name):
        if self.start._default_values:
            return self.start._default_values

    def transition_select_account(self):
        Fee = Pool().get('account.fee')
        fees = Fee.search([('broker_fee', '=', True)])
        accounts = set([])
        for f in fees:
            if f.product and f.product.template and \
                    f.product.template.account_expense_used:
                accounts.add(f.product.template.account_expense_used)
        self.start.broker_fees_accounts = list(accounts)
        if len(self.start.broker_fees_accounts) == 1:
            self.start.broker_fees_account = self.start.broker_fees_accounts[0]
            return 'show'
        return 'start'

    def get_broker_fees_paid(self, broker_party):
        MoveLine = Pool().get('account.move.line')
        move_lines = MoveLine.search([
                ('broker_fee_invoice_line.invoice.state', '=', 'paid'),
                ('party', '=', broker_party.id),
                ('account', '=', self.start.broker_fees_account.id),
                ('journal.type', '!=', 'commission',)
                ])
        return -1 * sum([x.amount for x in move_lines])

    def get_broker_fees_to_pay(self, broker_party):
        MoveLine = Pool().get('account.move.line')
        move_lines = MoveLine.search([
                (['OR', ('broker_fee_invoice_line', '=', None),
                        ('broker_fee_invoice_line.invoice.state', '=',
                            'posted'),
                        ]),
                ('party', '=', broker_party.id),
                ('account', '=', self.start.broker_fees_account.id),
                ('journal.type', '!=', 'commission',)
                ])
        return -1 * sum([x.amount for x in move_lines])

    def get_commissions_paid(self, broker_party, currency):
        cursor = Transaction().connection.cursor()
        pool = Pool()
        Commission = pool.get('commission')
        Invoice = pool.get('account.invoice')
        InvoiceLine = pool.get('account.invoice.line')
        Agent = pool.get('commission.agent')

        commission = Commission.__table__()
        invoice = Invoice.__table__()
        invoice_line = InvoiceLine.__table__()
        agent = Agent.__table__()

        query = commission.join(invoice_line,
            condition=commission.invoice_line == invoice_line.id
            ).join(invoice, condition=invoice_line.invoice == invoice.id
            ).join(agent, condition=commission.agent == agent.id
            ).select(
                ToChar(invoice.invoice_date, 'YYYY').as_('year'),
                Sum(commission.amount),
                where=((invoice.state == 'paid') &
                    (agent.party == broker_party.id)),
                group_by=[ToChar(invoice.invoice_date, 'YYYY')],
                order_by=[ToChar(invoice.invoice_date, 'YYYY').desc])
        cursor.execute(*query)
        res = []
        for year, amount in cursor.fetchall():
            res.append({
                    'year': year,
                    'amount': amount,
                    'currency_symbol': currency.symbol,
                    'currency_digits': currency.digits,
                    })
        total = [{
                'year': 'Total',
                'amount': sum([x['amount'] for x in res]),
                'currency_symbol': currency.symbol,
                'currency_digits': currency.digits,
                }]
        return total + res

    def get_commissions_to_pay(self, broker_party):
        commissions = Pool().get('commission').search([
                ('broker', '=', broker_party.network[0].id),
                ['OR', ('invoice_line', '=', None),
                    ('invoice_line.invoice.state', '=', 'posted')],
                ])
        return sum([c.amount for c in commissions])

    def default_show(self, name):
        Party = Pool().get('party.party')
        assert Transaction().context.get('active_model') == 'party.party'
        broker_party = Party(Transaction().context.get('active_id'))
        currency = self.start.broker_fees_account.currency
        commissions_paid = self.get_commissions_paid(broker_party, currency)
        return {
            'broker_fees_paid': self.get_broker_fees_paid(broker_party),
            'broker_fees_to_pay': self.get_broker_fees_to_pay(broker_party),
            'commissions_paid': commissions_paid[0]['amount'],
            'commissions_to_pay': self.get_commissions_to_pay(broker_party),
            'commissions_paid_details': commissions_paid,
            'currency': currency.id,
        }


class OpenCommissionsSynthesisStart(model.CoogView):
    'Open Commissions Synthesis Start'

    __name__ = 'commission.synthesis.start'

    broker_fees_account = fields.Many2One('account.account',
        'Broker fees account', required=True,
        domain=[('id', 'in', Eval('broker_fees_accounts'))],
        depends=['broker_fees_accounts'])
    broker_fees_accounts = fields.Many2Many('account.account', None, None,
        'Broker Fees Accounts')
    company = fields.Many2One('company.company', 'Company', required=True,
        states={'invisible': True})

    @staticmethod
    def default_company():
        return Transaction().context.get('company')


class OpenCommissionsSynthesisShow(model.CoogView, ModelCurrency):
    'Open Commissions Synthesis Show'

    __name__ = 'commission.synthesis.show'

    broker_fees_paid = fields.Numeric('Broker fees paid',
        digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits'], readonly=True)
    broker_fees_to_pay = fields.Numeric('Broker fees to pay',
        digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits'], readonly=True)
    commissions_paid = fields.Numeric('Commissions paid',
        digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits'], readonly=True)
    commissions_to_pay = fields.Numeric('Commissions to pay',
        digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits'], readonly=True)
    commissions_paid_details = fields.One2Many(
        'commission.synthesis.year_line', None, 'Commissions paid by year',
        readonly=True)


class OpenCommissionSynthesisYearLine(model.CoogView):
    'Open Commissions Synthesis Year Line'

    __name__ = 'commission.synthesis.year_line'

    year = fields.Char('Year')
    amount = fields.Numeric('Amount', digits=(16, Eval('currency_digits', 2)),
         depends=['currency_digits'], readonly=True)
    currency_symbol = fields.Char('Symbol')
    currency_digits = fields.Integer('Currency Digits')


class FilterCommissions(Wizard):
    'Commissions'

    __name__ = 'commission.filter_commission'

    start_state = 'choose_action'
    choose_action = StateTransition()
    filter_commission = StateAction('commission.act_commission_form')
    aggregated_commissions = StateAction(
        'commission_insurance.act_commission_aggregated_form_relate')

    def get_domain_from_invoice_business_kind(self, ids, kinds):
        in_domain = [('invoice_line.invoice', 'in', ids)]
        out_domain = [('origin.invoice', 'in', ids, 'account.invoice.line')]
        if len(kinds) != 1:
            return ['OR', in_domain[0], out_domain[0]]
        kind = kinds[0]
        if kind in ['broker_invoice', 'insurer_invoice']:
            return in_domain
        return out_domain

    def transition_choose_action(self):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        active_ids = Transaction().context.get('active_ids')
        active_model = Transaction().context.get('active_model')
        assert active_model in ['account.invoice', 'contract']
        if active_model == 'contract':
            invoices = Invoice.search([
                    ('contract', 'in', active_ids)])
            if not invoices:
                raise ValidationError(gettext(
                        'commission_insurance.msg_no_invoices'))
            return 'aggregated_commissions'
        ids = Transaction().context.get('active_ids')
        AccountInvoice = Pool().get('account.invoice')
        kinds = set([x.business_kind for x in AccountInvoice.browse(ids)])
        if len(kinds) != 1:
            return 'filter_commission'
        if kinds == {'contract_invoice'}:
            return 'aggregated_commissions'
        return 'filter_commission'

    def do_filter_commission(self, action):
        assert Transaction().context.get('active_model') == 'account.invoice'
        ids = Transaction().context.get('active_ids')
        AccountInvoice = Pool().get('account.invoice')
        kinds = set([x.business_kind for x in AccountInvoice.browse(ids)])
        domain = self.get_domain_from_invoice_business_kind(ids, list(kinds))
        action.update({
                'pyson_domain': PYSONEncoder().encode(domain)
                })
        return action, {}

    def do_aggregated_commissions(self, action):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        active_model = Transaction().context.get('active_model')
        active_ids = Transaction().context.get('active_ids')
        if active_model == 'contract':
            invoices = Invoice.search([
                    ('contract', 'in', active_ids)])
        else:
            invoices = Invoice.browse(active_ids)
        return action, {
            'extra_context': {
                'origins': [str(x) for invoice in invoices
                    for x in invoice.lines]},
            }


class FilterAggregatedCommissions(Wizard):
    'Filter Commissions aggregated'

    __name__ = 'commission.aggregated.open_detail'

    start_state = 'filter_commission'
    filter_commission = StateAction('commission.act_commission_form')

    def do_filter_commission(self, action):
        # The following active_id represents the max commission id and the
        # intermediate sql-view object id. See AggregatedCommission.table_query
        commission = Pool().get('commission')(
            Transaction().context.get('active_id'))
        invoice = commission.origin.invoice

        domain = [('agent', '=', commission.agent.id),
            ('origin', 'in', [str(line) for line in invoice.lines])]

        action.update({'pyson_domain': PYSONEncoder().encode(domain)})
        return action, {}


class ChangeBroker(Wizard):
    'Change Broker'

    __name__ = 'commission.change_broker'

    start_state = 'select_new_broker'
    select_new_broker = StateView('commission.change_broker.select_new_broker',
        'commission_insurance.select_new_broker_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Next', 'change', 'tryton-go-next', default=True),
            ])
    change = StateTransition()

    def default_select_new_broker(self, name):
        pool = Pool()
        cur_model = Transaction().context.get('active_model')
        cur_id = Transaction().context.get('active_id')
        defaults = {
            'at_date': utils.today(),
            }
        if cur_model == 'party.party':
            party = pool.get(cur_model)(cur_id)
            if party.is_broker:
                defaults['from_broker'] = party.id
        elif cur_model == 'distribution.network':
            dist_network = pool.get(cur_model)(cur_id)
            if dist_network.is_broker:
                defaults['from_broker'] = dist_network.party.id
        return defaults

    def transition_change(self):
        pool = Pool()
        Contract = pool.get('contract')
        if self.select_new_broker.all_contracts:
            contracts = Contract.search([
                    ('agent.party', '=',
                        self.select_new_broker.from_broker.id),
                    ('end_date', '>=', self.select_new_broker.at_date)])
        else:
            contracts = self.select_new_broker.contracts

        dist_network_id = None
        if self.select_new_broker.new_dist_network:
            dist_network_id = self.select_new_broker.new_dist_network.id
        Contract.change_broker(contracts, self.select_new_broker.to_broker,
            self.select_new_broker.at_date, update_contracts=True,
            dist_network=dist_network_id,
            create_missing=self.select_new_broker.auto_create_agents)
        return 'end'


class SelectNewBroker(model.CoogView):
    'Select New Broker'

    __name__ = 'commission.change_broker.select_new_broker'

    at_date = fields.Date('At Date', required=True)
    from_broker = fields.Many2One('party.party', 'From Broker',
        domain=[('is_broker', '=', True)], required=True)
    to_broker = fields.Many2One('party.party', 'To Broker',
        domain=[('is_broker', '=', True), ('id', '!=', Eval('from_broker'))],
        depends=['from_broker'], required=True)
    all_contracts = fields.Boolean('Change All Contracts')
    contracts = fields.Many2Many('contract', None, None, 'Contracts',
        domain=[('agent.party', '=', Eval('from_broker'))],
        states={'invisible': Eval('all_contracts', False),
            'required': ~Eval('all_contracts')},
        depends=['all_contracts', 'from_broker'])
    new_dist_network = fields.Many2One('distribution.network',
        'New Distributor',
        domain=[('party', '=', None),
            ('parent_party', '=', Eval('to_broker'))],
        states={'readonly': ~Eval('to_broker')}, depends=['to_broker'],)
    auto_create_agents = fields.Boolean('Auto Create Missing Agents')

    @fields.depends('all_contracts', 'contracts')
    def on_change_all_contracts(self):
        if self.all_contracts:
            self.contracts = []

    @fields.depends('all_contracts', 'from_broker', 'new_dist_network',
        'to_broker')
    def on_change_from_broker(self):
        self.contracts = []
        if self.from_broker == self.to_broker:
            self.to_broker = None
            self.new_dist_network = None

    @fields.depends('new_dist_network')
    def on_change_to_broker(self):
        self.new_dist_network = None


class AggregatedCommissionByAgent(model.CoogSQL, model.CoogView):
    'Commission Aggregated By Agent'

    __name__ = 'commission.aggregated.agent'

    agent = fields.Many2One('commission.agent', 'Agent', readonly=True)
    agent_name = fields.Function(
        fields.Char('Agent Name'),
        'get_agent_name', searcher='search_agent')
    party = fields.Many2One('party.party', 'Party', readonly=True)
    date = fields.Date('Date', readonly=True)
    broker = fields.Function(
        fields.Many2One('distribution.network', 'Broker', readonly=True),
        'get_broker', searcher='search_broker')
    amount = fields.Numeric('Amount', readonly=True, digits=price_digits)

    @classmethod
    def __setup__(cls):
        super(AggregatedCommissionByAgent, cls).__setup__()
        cls._order = [('agent', 'DESC'), ('date', 'ASC')]

    def get_agent_name(self, name):
        return self.agent.rec_name

    @classmethod
    def search_agent(cls, name, clause):
        return [('agent',) + tuple(clause[1:])]

    def get_broker(self, name):
        return (self.agent.party.network[0].id
            if self.agent and self.agent.party.is_broker else None)

    @classmethod
    def search_broker(cls, name, clause):
        return ['AND',
            [('agent.party.network',) + tuple(clause[1:])],
            [('agent.party.network.is_broker', '=', True)]]

    @classmethod
    def get_tables(cls):
        pool = Pool()
        commission = pool.get('commission').__table__()
        agent = pool.get('commission.agent').__table__()
        return {
            'commission': commission,
            'commission.agent': agent
            }

    @classmethod
    def get_query_table(cls, tables):
        commission = tables['commission']
        agent = tables['commission.agent']
        return commission.join(agent, condition=commission.agent == agent.id)

    @classmethod
    def get_where_clause(cls, tables):
        return None

    @classmethod
    def get_fields_to_select(cls, tables):
        commission = tables['commission']
        agent = tables['commission.agent']

        return (
            Max(commission.id).as_('id'),
            agent.party.as_('party'),
            Literal(0).as_('create_uid'),
            Min(commission.create_date).as_('create_date'),
            Literal(0).as_('write_uid'),
            Max(commission.write_date).as_('write_date'),
            commission.agent.as_('agent'),
            commission.date.as_('date'),
            Sum(commission.amount).as_('amount'))

    @classmethod
    def get_group_by(cls, tables):
        commission = tables['commission']
        agent = tables['commission.agent']
        return [commission.agent, agent.party, commission.date]

    @staticmethod
    def table_query():
        klass = Pool().get('commission.aggregated.agent')
        tables = klass.get_tables()
        query_table = klass.get_query_table(tables)

        return query_table.select(*klass.get_fields_to_select(tables),
            where=klass.get_where_clause(tables),
            group_by=klass.get_group_by(tables))


class CommissionDescriptionConfiguration(ModelSingleton, model.CoogSQL,
        model.CoogView, export.ExportImportMixin):
    'Commission Description Configuration'

    __name__ = 'commission.description.configuration'

    linear_commission_title = fields.Char(
        'Linear Commission Title', help='Contains the string which will '
        'be used to introduce linear commissions calculation details',
        required=True, translate=True)

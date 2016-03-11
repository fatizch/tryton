import datetime
from dateutil import rrule

from sql import Cast, Literal
from sql.operators import Concat
from sql.aggregate import Sum, Max, Min
from sql.functions import ToChar
from sql.conditionals import Coalesce

from trytond import backend
from trytond.pool import PoolMeta, Pool
from trytond.model import Unique
from trytond.pyson import Eval, Bool, PYSONEncoder
from trytond.wizard import Wizard, StateView, Button, StateTransition
from trytond.wizard import StateAction
from trytond.transaction import Transaction
from trytond.tools import grouped_slice
from trytond.cache import Cache

from trytond.modules.cog_utils import (fields, model, export, coop_string,
    coop_date, utils)
from trytond.modules.currency_cog import ModelCurrency

__all__ = [
    'PlanLines',
    'PlanLinesCoverageRelation',
    'Commission',
    'AggregatedCommission',
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
    ]
__metaclass__ = PoolMeta


class Commission:
    __name__ = 'commission'
    commissioned_contract = fields.Function(
        fields.Many2One('contract', 'Commissioned Contract'),
        'get_commissioned_contract', searcher='search_commissioned_contract')
    commissioned_option = fields.Many2One('contract.option',
        'Commissioned Option', select=True, ondelete='RESTRICT')
    party = fields.Function(
        fields.Many2One('party.party', 'Party'),
        'get_party', searcher='search_party')
    broker = fields.Function(
        fields.Many2One('distribution.network', 'Broker'),
        'get_broker', searcher='search_broker')
    commission_rate = fields.Numeric('Commission Rate', digits=(16, 4))
    base_amount = fields.Function(
        fields.Numeric('Base Amount'),
        'get_base_amount')
    commissioned_subscriber = fields.Function(
        fields.Many2One('party.party', 'Contract Subscriber'),
        'get_commissioned_subscriber',
        searcher='search_commissioned_subscriber')
    start = fields.Date('Start')
    end = fields.Date('End')

    @classmethod
    def __register__(cls, module_name):
        # Migration from 1.4: add commissioned_option, start, end
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().cursor
        commission = TableHandler(cursor, cls)
        has_option_column = commission.column_exist('commissioned_option')
        has_start_column = commission.column_exist('start')

        super(Commission, cls).__register__(module_name)
        if not has_option_column:
            cursor.execute("UPDATE commission "
                "SET commissioned_option = Cast(substring(origin,17) as int) "
                "WHERE origin LIKE 'contract.option,%'")
            cursor.execute("UPDATE commission c "
                "SET commissioned_option = d.option "
                "FROM account_invoice_line_detail d "
                "WHERE Cast(substring(c.origin,22) as int) = d.invoice_line "
                "AND d.option is not NULL "
                "AND c.origin LIKE 'account.invoice.line,%'")
            cursor.execute("UPDATE commission c "
                "SET commissioned_option = e.option "
                "FROM contract_option_extra_premium e INNER JOIN "
                "account_invoice_line_detail d on d.extra_premium = e.id "
                "WHERE Cast(substring(c.origin,22) as int) = d.invoice_line "
                "AND d.extra_premium is not NULL "
                "AND c.origin LIKE 'account.invoice.line,%'")
        if not has_start_column:
            commission = cls.__table__()
            line = Pool().get('account.invoice.line').__table__()
            update_table = commission.join(line,
                condition=(Concat('account.invoice.line,', Cast(line.id,
                            'VARCHAR')) == commission.origin)
                ).select(commission.id, line.coverage_start.as_('start'),
                    line.coverage_end.as_('end'))
            commission_up = cls.__table__()
            cursor.execute(*commission_up.update(
                    columns=[commission_up.start, commission_up.end],
                    values=[update_table.start, update_table.end],
                    from_=[update_table],
                    where=(commission_up.id == update_table.id)))
        # Migration from 1.6: store commission_rate as percent
        commission = cls.__table__()
        rate_not_as_percent_query = commission.select(commission.id,
            where=(commission.commission_rate >= 1), limit=1)
        cursor.execute(*rate_not_as_percent_query)
        if len(cursor.fetchall()):
            commission = cls.__table__()
            cursor.execute(*commission.update(
                    columns=[commission.commission_rate],
                    values=[Cast(commission.commission_rate / 100,
                        'DECIMAL (16,4)')]))

    @classmethod
    def __setup__(cls):
        super(Commission, cls).__setup__()
        cls.amount.digits = (16, 8)
        cls.invoice_line.select = True
        cls.type_.searcher = 'search_type_'

    def get_commissioned_contract(self, name):
        if self.commissioned_option:
            return self.commissioned_option.parent_contract.id

    def get_base_amount(self, name):
        return getattr(self.origin, 'amount', 0)

    @classmethod
    def search_commissioned_contract(cls, name, clause):
        return [('commissioned_option.parent_contract',) +
            tuple(clause[1:])]

    def get_commissioned_subscriber(self, name):
        if self.commissioned_option:
            return self.commissioned_option.parent_contract.subscriber.id

    @classmethod
    def search_commissioned_subscriber(cls, name, clause):
        return [('commissioned_option.parent_contract.subscriber',) +
            tuple(clause[1:])]

    def get_party(self, name):
        return self.agent.party.id if self.agent else None

    def get_broker(self, name):
        return (self.agent.party.network[0].id
            if self.agent and self.agent.party.network else None)

    @classmethod
    def _get_invoice(cls, key):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        AccountConfiguration = pool.get('account.configuration')

        party = key['party']
        if key['type'].startswith('out'):
            payment_term = party.customer_payment_term
        else:
            payment_term = party.supplier_payment_term
        if not payment_term:
            conf = AccountConfiguration(1)
            payment_term = conf.commission_invoice_payment_term
        return Invoice(
            company=key['company'],
            type=key['type'],
            journal=cls.get_journal(),
            party=party,
            invoice_address=party.address_get(type='invoice'),
            currency=key['currency'],
            account=key['account'],
            payment_term=payment_term,
            )

    def _group_to_invoice_key(self):
        direction = {
            'in': 'out',
            'out': 'in',
            }.get(self.type_)
        document = 'invoice'
        return (('party', self.agent.party),
            ('type', '%s_%s' % (direction, document)),
            ('company', self.agent.company),
            ('currency', self.agent.currency),
            ('account', self.agent.account),
            )

    def _group_to_invoice_line_key(self):
        return super(Commission, self)._group_to_invoice_line_key() + (
            ('agent', self.agent),)

    @classmethod
    def invoice(cls, commissions):
        pool = Pool()
        Fee = pool.get('account.fee')
        super(Commission, cls).invoice(commissions)
        invoices = list(set([c.invoice_line.invoice for c in commissions]))
        Fee.add_broker_fees_to_invoice(invoices)
        return invoices

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
        return [('agent.party.network',) + tuple(clause[1:])],

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
                line.amount *= -1
                to_save.append(line)
            for line in cls.copy(to_cancel):
                line.agent = new_agent
                to_save.append(line)
            cls.save(to_save)


class AggregatedCommission(model.CoopSQL, model.CoopView):
    'Commission Aggregated'

    __name__ = 'commission.aggregated'

    agent = fields.Many2One('commission.agent', 'Agent', readonly=True)
    party = fields.Many2One('party.party', 'Party', readonly=True)
    invoice = fields.Many2One('account.invoice', 'Invoice', readonly=True)
    date = fields.Date('Date', readonly=True)
    contract = fields.Function(
        fields.Many2One('contract', 'Contract', readonly=True),
        'get_commissioned_contract', searcher='search_commissioned_contract')
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
                ], 'State', readonly=True),
        'get_invoice_state')

    def get_commissioned_contract(self, name=None):
        if self.commissioned_option:
            return self.commissioned_option.parent_contract.id
        return None

    @classmethod
    def search_commissioned_contract(cls, name, clause):
        return [('commissioned_option.parent_contract',) +
            tuple(clause[1:])]

    def get_currency_digits(self, name):
        return self.invoice.currency_digits if self.invoice else 2

    @classmethod
    def __setup__(cls):
        super(AggregatedCommission, cls).__setup__()
        cls._order = [('total_commission', 'DESC')]

    def get_broker(self, name):
        return (self.agent.party.network[0].id
            if self.agent and self.agent.party.network else None)

    @classmethod
    def search_broker(cls, name, clause):
        return [('agent.party.network',) + tuple(clause[1:])],

    def get_subscriber(self, name):
        if self.contract:
            return self.contract.subscriber.id

    @classmethod
    def search_commissioned_subscriber(cls, name, clause):
        return [('contract.subscriber',) + tuple(clause[1:])]

    def get_invoice_state(self, name=None):
        return self.invoice.state if self.invoice else None

    @staticmethod
    def table_query():
        pool = Pool()
        Agent = pool.get('commission.agent')
        InvoiceLine = pool.get('account.invoice.line')
        commission = pool.get('commission').__table__()
        agent = Agent.__table__()
        invoice_line = InvoiceLine.__table__()

        commission_agent = commission.join(agent,
            condition=commission.agent == agent.id)

        per_agent = commission_agent.join(invoice_line, type_='LEFT OUTER',
                condition=(commission.origin == Concat('account.invoice.line,',
                Cast(invoice_line.id, 'VARCHAR')))
                )

        return per_agent.select(
            Max(commission.id).as_('id'),
            agent.party.as_('party'),
            invoice_line.invoice.as_('invoice'),
            Literal(0).as_('create_uid'),
            Literal(0).as_('create_date'),
            Literal(0).as_('write_uid'),
            Literal(0).as_('write_date'),
            commission.agent.as_('agent'),
            Max(commission.commissioned_option).as_('commissioned_option'),
            Min(commission.start).as_('start'),
            Max(commission.end).as_('end'),
            Max(commission.date).as_('date'),
            Sum(commission.amount).as_('total_commission'),
            group_by=[commission.agent, invoice_line.invoice, agent.party])


class Plan(export.ExportImportMixin, model.TaggedMixin):
    __name__ = 'commission.plan'
    _func_key = 'code'

    code = fields.Char('Code', required=True)
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
    def default_type_():
        return 'agent'

    def get_context_formula(self, amount, product, pattern=None):
        context = super(Plan, self).get_context_formula(amount, product)
        context['names']['nb_years'] = (pattern or {}).get('nb_years', 0)
        context['names']['invoice_line'] = (pattern or {}).get('invoice_line',
            None)
        return context

    def compute(self, amount, product, pattern=None):
        'Compute commission amount for the amount'
        if pattern is None:
            pattern = {}
        pattern['product'] = product.id if product else None
        context = self.get_context_formula(amount, product, pattern)
        for line in self.lines:
            if line.match(pattern):
                return line.get_amount(**context)

    @classmethod
    def is_master_object(cls):
        return True

    @fields.depends('code', 'name')
    def on_change_with_code(self):
        if self.code:
            return self.code
        return coop_string.slugify(self.name)

    def get_commissioned_products(self, name):
        products = []
        for line in self.lines:
            for option in line.options:
                products.extend([product.id for product in option.products])
        return list(set(products))

    def get_commissioned_products_name(self, name):
        return ', '.join([x.name for x in self.commissioned_products])

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
                        coop_date.add_day(all_dates[idx + 1], -1)))
        return periods

    def get_commission_dates(self, invoice_line):
        all_dates = {invoice_line.coverage_start, invoice_line.coverage_end}
        for date_line in self.computation_dates:
            all_dates |= date_line.get_dates(invoice_line)
        return sorted(list(all_dates))


class PlanLines(export.ExportImportMixin):
    __name__ = 'commission.plan.line'

    options = fields.Many2Many(
        'commission.plan.lines-offered.option.description', 'plan_line',
        'option', 'Options')
    options_extract = fields.Function(fields.Text('Options'),
        'get_options_extract')
    _get_matching_cache = Cache('get_matching_cache')

    @classmethod
    def create(cls, vlist):
        super(PlanLines, cls).create(vlist)
        cls._get_matching_cache.clear()

    @classmethod
    def write(cls, *args):
        super(PlanLines, cls).write(*args)
        cls._get_matching_cache.clear()

    @classmethod
    def delete(cls, plan_lines):
        super(PlanLines, cls).delete(plan_lines)
        cls._get_matching_cache.clear()

    def match(self, pattern):
        if 'coverage' not in pattern:
            if 'product' in pattern and self.product:
                return pattern['product'] == self.product.id
            else:
                return False
        coverage_id = pattern['coverage'].id
        key = (self.id, coverage_id)
        option_ids = self._get_matching_cache.get(key, -1)

        if option_ids != -1:
            return coverage_id in option_ids

        option_ids = {o.id for o in self.options}
        self._get_matching_cache.set(key, option_ids)
        return coverage_id in option_ids

    def get_options_extract(self, name):
        return ' \n'.join((option.name for option in self.options))

    @classmethod
    def _export_light(cls):
        return (super(PlanLines, cls)._export_light() | set(['options']))

    def get_func_key(self, name):
        return self.options_extract


class PlanLinesCoverageRelation(model.CoopSQL, model.CoopView):
    'Commission Plan Line - Offered Option Description'

    __name__ = 'commission.plan.lines-offered.option.description'

    plan_line = fields.Many2One('commission.plan.line', 'Plan Line',
        ondelete='CASCADE')
    option = fields.Many2One('offered.option.description', 'Option',
        ondelete='RESTRICT')


class PlanRelation(model.CoopSQL, model.CoopView):
    'Commission Plan - Commission Plan'

    __name__ = 'commission_plan-commission_plan'

    from_ = fields.Many2One('commission.plan', 'Plan', ondelete='CASCADE')
    to = fields.Many2One('commission.plan', 'Plan', ondelete='RESTRICT')


class PlanCalculationDate(model.CoopSQL, model.CoopView):
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
    def __setup__(cls):
        super(PlanCalculationDate, cls).__setup__()
        cls._error_messages.update({
                'need_date_field_set': 'Some date fields must be set',
                'invalid_month_day_combination':
                'Invalid Month (%s) Day (%s) Combination',
                })

    @classmethod
    def validate(cls, dates):
        for date in dates:
            if date.type_ == 'relative':
                if not date.day and not date.month and not date.year:
                    cls.raise_user_error('need_date_field_set')
            elif date.type_ == 'absolute':
                try:
                    date = datetime.date(2000, int(date.month), int(date.day))
                except ValueError:
                    cls.raise_user_error('invalid_month_day_combination',
                        (date.month, date.day))

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
                    date = getattr(coop_date, 'add_%s' % fname)(date,
                        int(value))
                values.append(date)
        if not values:
            # invoice_line in the past following a start_date modification for
            # instance
            return set()
        if self.first_match_only:
            values = [values[0]]
        return {x for x in values if x > invoice_line.coverage_start
            and x < invoice_line.coverage_end}

    def get_rrule_frequency(self):
        if self.frequency == 'yearly':
            return rrule.YEARLY
        if self.frequency == 'monthly':
            return rrule.MONTHLY

    def get_reference_date(self, invoice_line):
        if self.reference_date == 'contract_start':
            return invoice_line.invoice.contract.start_date
        if self.reference_date == 'contract_signature':
            return invoice_line.invoice.contract.dignature_date
        if self.reference_date == 'option_start':
            return invoice_line.details[0].get_option().start_date


class Agent(export.ExportImportMixin, model.FunctionalErrorMixIn):
    __name__ = 'commission.agent'
    _func_key = 'func_key'

    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    func_key = fields.Function(fields.Char('Functional Key'),
        'get_func_key', searcher='search_func_key')

    @classmethod
    def __setup__(cls):
        super(Agent, cls).__setup__()
        cls.plan.domain = [('type_', '=', Eval('type_'))]
        cls.plan.depends = ['type_']
        cls.plan.required = True
        cls.plan.select = True
        cls.party.select = True
        cls._error_messages.update({
                'agent_not_found': 'Cannot find matching agent for %s :\n\n%s',
                })

    @classmethod
    def is_master_object(cls):
        return True

    @classmethod
    def _export_light(cls):
        return (super(Agent, cls)._export_light() |
            set(['company', 'currency', 'plan']))

    def get_func_key(self, name):
        return '%s|%s' % ((self.party.code, self.plan.code))

    def get_rec_name(self, name):
        return self.plan.rec_name

    @classmethod
    def search_func_key(cls, name, clause):
        assert clause[1] == '='
        if '|' in clause[2]:
            operands = clause[2].split('|')
            if len(operands) == 2:
                party_code, plan_code = clause[2].split('|')
                return [('party.code', clause[1], party_code),
                    ('plan.code', clause[1], plan_code)]
            elif len(operands) == 3:
                party_code, plan_code, product_code = clause[2].split('|')
                domain = []
                if party_code:
                    domain.append(('party.code', clause[1], party_code))
                if plan_code:
                    domain.append(('plan.code', clause[1], plan_code))
                if product_code:
                    domain.append(('plan.commissioned_products.code',
                            clause[1], product_code))
                return domain
            else:
                return [('id', '=', None)]
        else:
            return ['OR',
                [('party.code',) + tuple(clause[1:])],
                [('plan.code',) + tuple(clause[1:])],
                ]

    @classmethod
    def find_matches(cls, agents, target_broker):
        source_keys = {agent: agent.get_hash() for agent in agents}
        target_keys = {agent.get_hash(): agent
            for agent in target_broker.agents}
        matches = {}
        for source_agent, source_key in source_keys.iteritems():
            matches[source_agent] = target_keys.get(source_key, None)
        return matches

    @classmethod
    def format_hash(cls, hash_dict):
        return coop_string.translate_label(cls, 'plan') + ' : ' + \
            hash_dict['plan'].rec_name

    def get_hash(self):
        return (('plan', self.plan),)

    def copy_to_broker(self, target_broker):
        return self.copy([self], default={'party': target_broker.id})[0]


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
                    'account_payable': self.parties.account_payable.id,
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


class CreateAgentsParties(model.CoopView):
    'Create Agents'

    __name__ = 'commission.create_agents.parties'

    company = fields.Many2One('company.company', 'Company', required=True)
    parties = fields.Many2Many('party.party', None, None, 'Parties',
        domain=[
            ('is_company', '=', True),
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


class CreateAgentsAsk(model.CoopView):
    'Create Agents'

    __name__ = 'commission.create_agents.ask'

    company = fields.Many2One('company.company', 'Company', required=True)
    brokers = fields.Many2Many('distribution.network', None, None, 'Brokers',
        domain=[('party', '!=', None)], required=True)
    plans = fields.Many2Many('commission.plan', None, None, 'Plans',
        domain=[('type_', '=', 'agent')], required=True)

    @staticmethod
    def default_company():
        return Transaction().context.get('company')


class CreateInvoice:
    __name__ = 'commission.create_invoice'

    def do_create_(self, action):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        Commission = pool.get('commission')
        commissions = Commission.search(self.get_domain(),
            order=[('agent', 'DESC'), ('date', 'DESC')])
        invoices = Commission.invoice(commissions)
        Invoice.write(invoices, {'invoice_date': self.ask.to})
        if self.ask.post_invoices:
            Invoice.post(invoices)
        encoder = PYSONEncoder()
        action['pyson_domain'] = encoder.encode(
            [('id', 'in', [i.id for i in invoices])])
        action['pyson_search_value'] = encoder.encode([])
        return action, {}

    def get_domain(self):
        domain = super(CreateInvoice, self).get_domain()
        if not self.ask.all_brokers:
            domain.append(('agent.party', 'in', self.ask.brokers))
        return domain


class CreateInvoiceAsk:
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
        cls.type_.states = {'invisible': True}
        super(CreateInvoiceAsk, cls).__setup__()

    @staticmethod
    def default_type_():
        return 'out'

    @staticmethod
    def default_all_brokers():
        return True


class OpenCommissionsSynthesis(Wizard):
    'Open Commissions Synthesis'

    __name__ = 'commission.synthesis'

    start_state = 'start'
    start = StateView('commission.synthesis.start',
        'commission_insurance.synthesis_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Show', 'show', 'tryton-go-next', default=True),
            ])
    show = StateView('commission.synthesis.show',
        'commission_insurance.synthesis_show_view_form', [
            Button('Ok', 'end', 'tryton-ok', default=True),
            ])

    def get_broker_fees_paid(self, broker_party):
        MoveLine = Pool().get('account.move.line')
        move_lines = MoveLine.search([
                ('broker_fee_invoice_line.invoice.state', '=', 'paid'),
                ('party', '=', broker_party.id),
                ('account', '=', self.start.broker_fees_account.id),
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
                ])
        return -1 * sum([x.amount for x in move_lines])

    def get_commissions_paid(self, broker_party, currency):
        cursor = Transaction().cursor
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
                where=((invoice.state == 'paid')
                    & (agent.party == broker_party.id)),
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


class OpenCommissionsSynthesisStart(model.CoopView):
    'Open Commissions Synthesis Start'

    __name__ = 'commission.synthesis.start'

    broker_fees_account = fields.Many2One('account.account',
        'Broker fees account', required=True,
        domain=[('company', '=', Eval('company'))], depends=['company'],
    )
    company = fields.Many2One('company.company', 'Company', required=True,
        states={'invisible': True})

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_broker_fees_account():
        Fee = Pool().get('account.fee')
        fees = Fee.search([('broker_fee', '=', True)])
        for f in fees:
            if f.product and f.product.template and \
                    f.product.template.account_expense_used:
                return f.product.template.account_expense_used.id


class OpenCommissionsSynthesisShow(model.CoopView, ModelCurrency):
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


class OpenCommissionSynthesisYearLine(model.CoopView):
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

    start_state = 'filter_commission'
    filter_commission = StateAction('commission.act_commission_form')

    def do_filter_commission(self, action):
        assert Transaction().context.get('active_model') == 'account.invoice'
        ids = Transaction().context.get('active_ids')
        AccountInvoice = Pool().get('account.invoice')
        in_domain = [('invoice_line.invoice', 'in', ids)]
        out_domain = [('origin.invoice', 'in', ids, 'account.invoice.line')]
        types = set([x.type for x in AccountInvoice.browse(ids)])
        if len(types) != 1:
            domain = ['OR', in_domain[0], out_domain[0]]
        elif types == {'in_invoice'}:
            domain = in_domain
        else:
            domain = out_domain
        action.update({
                'pyson_domain': PYSONEncoder().encode(domain)
                })
        return action, {}


class FilterAggregatedCommissions(Wizard):
    'Filter Commissions aggregated'

    __name__ = 'commission.aggregated.open_detail'

    start_state = 'filter_commission'
    filter_commission = StateAction('commission.act_commission_form')

    def do_filter_commission(self, action):
        # The following active_id represents the max commission id and the
        # intermediate sql-view object id (See AggregatedCommission.table_query).
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
            party = pool.get(cur_model)(cur_id).party
            defaults['from_broker'] = party.id
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

        agency_id = None
        if self.select_new_broker.new_agency:
            agency_id = self.select_new_broker.new_agency.id
        Contract.change_broker(contracts, self.select_new_broker.to_broker,
            self.select_new_broker.at_date, update_contracts=True,
            agency=agency_id,
            create_missing=self.select_new_broker.auto_create_agents)
        return 'end'


class SelectNewBroker(model.CoopView):
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
    new_agency = fields.Many2One('distribution.network', 'New Agency',
        domain=[('party', '=', None),
            ('parent_party', '=', Eval('to_broker'))],
        states={'readonly': ~Eval('to_broker')}, depends=['to_broker'],)
    auto_create_agents = fields.Boolean('Auto Create Missing Agents')

    @fields.depends('all_contracts', 'contracts')
    def on_change_all_contracts(self):
        if self.all_contracts:
            self.contracts = []

    @fields.depends('all_contracts', 'from_broker', 'new_agency', 'to_broker')
    def on_change_from_broker(self):
        self.contracts = []
        if self.from_broker == self.to_broker:
            self.to_broker = None
            self.new_agency = None

    @fields.depends('new_agency')
    def on_change_to_broker(self):
        self.new_agency = None

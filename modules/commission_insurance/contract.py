# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms
import datetime

from collections import defaultdict
from decimal import Decimal

from sql.operators import Concat

from trytond.i18n import gettext
from trytond.model.exceptions import ValidationError
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, If, Bool
from trytond.cache import Cache, freeze

from trytond.modules.coog_core import fields, utils, model
from trytond.modules.contract import _STATES, _DEPENDS

from trytond.modules.coog_core.coog_date import FREQUENCY_CONVERSION_TABLE

__all__ = [
    'Contract',
    'ContractOption',
    ]

ANNUAL_CONVERSION_TABLE = {
    'yearly': 1,
    'half_yearly': 2,
    'quaterly': 4,
    'monthly': 12,
    }


class Contract(metaclass=PoolMeta):
    __name__ = 'contract'

    broker = fields.Function(
        fields.Many2One('distribution.network', 'Broker',
            domain=[If(Bool(Eval('dist_network', False)),
                [('all_children', '=', Eval('dist_network'))],
                [('id', '=', None)]),
                ('party.agents', '!=', None)], states=_STATES,
            depends=_DEPENDS + ['dist_network']),
        'on_change_with_broker', 'setter_void')
    broker_party = fields.Function(
        fields.Many2One('party.party', 'Broker'),
        'on_change_with_broker_party', searcher='search_broker_party')
    agent = fields.Many2One('commission.agent', 'Agent', ondelete='RESTRICT',
        # Careful, any change in the depends for this domain should be
        # reflected in the on_change_broker / on_change_with_agent depends
        domain=[
            ('type_', '=', 'agent'),
            ('plan.commissioned_products', '=', Eval('product')),
            ('party', '=', Eval('broker_party')),
            If(Eval('status') == 'quote',
                [['OR',
                        ('end_date', '>=', Eval('appliable_conditions_date')),
                        ('end_date', '=', None),
                        ],
                    ['OR',
                        ('start_date', '<=', Eval('appliable_conditions_date')),
                        ('start_date', '=', None),
                ]], [])
            ],
        states=_STATES, depends=_DEPENDS + ['broker_party', 'product',
            'appliable_conditions_date', 'status'])
    insurer_agent_cache = Cache('contract_insurer_agent')

    @classmethod
    def _export_light(cls):
        return (super(Contract, cls)._export_light() | {'agent'})

    def get_invoice(self, start, end, billing_information):
        invoice = super(Contract, self).get_invoice(start, end,
            billing_information)
        invoice.agent = self.agent
        return invoice

    def find_insurer_agent_domain(self, option=None, line=None):
        domain = [('type_', '=', 'principal')]
        coverage = None
        date = None
        if self.agent and self.agent.plan.insurer_plan:
            domain.append(('plan', '=', self.agent.plan.insurer_plan))
        if not option and line and getattr(line, 'details', None):
            coverage = getattr(line.details[0], 'rated_entity', None)
            date = line.coverage_start
        elif option:
            coverage = option.coverage
            date = option.initial_start_date
        if (coverage and hasattr(coverage, 'get_insurer') and
                coverage.get_insurer(date)):
            domain.append(('party', '=', coverage.get_insurer(date).party))
        else:
            return None
        return domain

    def get_insurer_pattern(self, option=None, line=None):
        pattern = {'agent': self.agent}
        if self.agent and self.agent.plan.insurer_plan:
            pattern['plan'] = self.agent.plan.insurer_plan
        coverage = None
        date = None
        if not option and line:
            coverage = getattr(line.details[0], 'rated_entity', None)
            date = line.coverage_start
        if option:
            coverage = option.coverage
            date = option.initial_start_date
        if coverage:
            pattern['coverage'] = coverage
            insurer = coverage.get_insurer(date)
            if insurer:
                pattern['party'] = insurer.party
        return pattern

    def find_insurer_agent(self, option=None, line=None):
        pool = Pool()
        Agent = pool.get('commission.agent')
        domain = self.find_insurer_agent_domain(option, line)
        if not domain:
            return
        agents = Agent.search(domain)
        pattern = self.get_insurer_pattern(option, line)
        key = freeze((pattern, self.id))
        cached = self.insurer_agent_cache.get(key, default=False)
        if cached is not False:
            return Agent(cached)
        for agent in agents:
            for plan_line in agent.plan.lines:
                if plan_line.match(pattern):
                    self.insurer_agent_cache.set(key, agent.id)
                    return agent

    @classmethod
    def _finalize_invoices(cls, contract_invoices):
        super(Contract, cls)._finalize_invoices(contract_invoices)
        for contract_invoice in contract_invoices:
            invoice = contract_invoice.invoice
            for line in invoice.lines:
                line.principal = contract_invoice.contract.find_insurer_agent(
                    line=line)

    @fields.depends('agent', 'dist_network')
    def on_change_with_broker(self, name=None):
        if self.agent:
            return (self.agent.party.network[0].id
                if self.agent and self.agent.party.is_broker else None)
        elif self.dist_network and self.dist_network.parent_brokers:
            if len(self.dist_network.parent_brokers) == 1:
                return self.dist_network.parent_brokers[0].id

    @fields.depends('broker')
    def on_change_with_broker_party(self, name=None):
        return self.broker.party.id if self.broker else None

    @fields.depends('broker', 'agent', 'product',
        'appliable_conditions_date', 'status')
    def on_change_broker(self):
        # Careful with depends, some clients are depending on the current
        # behaviour
        self.broker_party = self.on_change_with_broker_party()
        if self.broker_party:
            self.agent = self.on_change_with_agent()

    @fields.depends('broker_party', 'product', 'appliable_conditions_date',
        'status')
    def on_change_with_agent(self):
        if self.product and self.appliable_conditions_date:
            return utils.auto_complete_with_domain(self, 'agent')

    @classmethod
    def change_broker(cls, contracts, new_broker, at_date,
            update_contracts=False, dist_network=None, create_missing=False):
        pool = Pool()
        Commission = pool.get('commission')
        Agent = pool.get('commission.agent')
        Event = pool.get('event')
        Invoice = pool.get('account.invoice')
        per_agent = defaultdict(list)
        [per_agent[contract.agent].append(contract) for contract in contracts]

        agent_matches = Agent.find_matches(list(per_agent.keys()), new_broker)

        to_create = []
        with model.error_manager():
            for src_agent, dest_agent in list(agent_matches.items()):
                if dest_agent:
                    continue
                if not create_missing:
                    raise ValidationError(gettext(
                            'commission_insurance.msg_agent_not_found',
                            broker=new_broker.rec_name,
                            agent=Agent.format_hash(
                                dict(src_agent.get_hash()))))
                    continue
                to_create.append(src_agent)
        if to_create:
            agent_matches.update({
                    src_agent: src_agent.copy_to_broker(new_broker)
                    for src_agent in to_create})

        for from_agent, to_agent in agent_matches.items():
            if update_contracts:
                cls.write(per_agent[from_agent], {'agent': to_agent.id,
                    'dist_network': dist_network})
            Commission.modify_agent(Commission.search([
                        ('commissioned_contract', 'in',
                            [x.id for x in per_agent[from_agent]]),
                        ('agent', '=', from_agent),
                        ('origin.coverage_start', '>=', at_date,
                            'account.invoice.line')]),
                to_agent)

            Invoice.modify_invoice_agent(Invoice.search([
                        ('contract', 'in',
                            [x.id for x in per_agent[from_agent]]),
                        ('agent', '=', from_agent),
                        ('start', '>=', at_date)]),
                to_agent)
        Event.notify_events(contracts, 'broker_changed')

    @classmethod
    def search_broker_party(cls, name, clause):
        return [('agent.party',) + tuple(clause[1:])]

    @staticmethod
    def order_broker_party(tables):
        broker_party_order = tables.get('broker_party_order_tables')
        if broker_party_order:
            return [broker_party_order[None][0].order]
        pool = Pool()
        table, _ = tables[None]
        contract = tables.get('contract')
        if contract is None:
            contract = pool.get('contract').__table__()
        party_relation = pool.get('party.party').__table__()
        agent_relation = pool.get('commission.agent').__table__()

        query = contract.join(agent_relation, condition=(
                contract.agent == agent_relation.id)
                ).join(party_relation, condition=(
                        agent_relation.party == party_relation.id)).select(
                            contract.id.as_('contract'),
                            Concat(party_relation.code,
                                party_relation.name).as_('order'))

        tables['broker_party_order_tables'] = {
            None: (query, (query.contract == table.id))
            }
        return [query.order]


class ContractOption(metaclass=PoolMeta):
    __name__ = 'contract.option'

    annual_premium_incl_tax = fields.Function(
        fields.Numeric('Annual Premium Including Taxes',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']),
        'get_premium')
    annual_premium_excl_tax = fields.Function(
        fields.Numeric('Annual Premium Excluding Taxes',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']),
        'get_premium')
    annual_taxes = fields.Function(
        fields.Numeric('Annual Taxes',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']),
        'get_premium')
    monthly_premium_incl_tax = fields.Function(
        fields.Numeric('Monthly Premium Including Taxes',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']),
        'get_premium')
    monthly_premium_excl_tax = fields.Function(
        fields.Numeric('Monthly Premium Excluding Taxes',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']),
        'get_premium')
    monthly_taxes = fields.Function(
        fields.Numeric('Monthly Taxes',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']),
        'get_premium')

    def get_void_premium(self, date):
        res = {
            'annual_void_premium_incl_tax': Decimal('0.0'),
            'annual_void_premium_excl_tax': Decimal('0.0'),
            'monthly_void_premium_incl_tax': Decimal('0.0'),
            'monthly_void_premium_excl_tax': Decimal('0.0'),
            }
        if not self.coverage.premium_rules:
            return res
        rule_dict_template = self.coverage.premium_rules[
            0].get_base_premium_dict(self)
        self.init_dict_for_rule_engine(rule_dict_template)
        rule_dict_template['date'] = date
        lines = self.coverage.premium_rules[0].do_calculate(rule_dict_template)
        for cur_line in lines:
            if (cur_line.amount and self.coverage.premium_rules[0].frequency in
                    ANNUAL_CONVERSION_TABLE):
                res['annual_void_premium_incl_tax'] += cur_line.amount * \
                    Decimal(ANNUAL_CONVERSION_TABLE[
                            self.coverage.premium_rules[0].frequency])
                res['monthly_void_premium_incl_tax'] += cur_line.amount / \
                    Decimal(FREQUENCY_CONVERSION_TABLE[
                            self.coverage.premium_rules[0].frequency])
        pool = Pool()
        Tax = pool.get('account.tax')
        InvoiceLine = pool.get('account.invoice.line')
        res['annual_void_premium_excl_tax'] = self.currency.round(
            Tax._reverse_unit_compute(res['annual_void_premium_incl_tax'],
                self.coverage.taxes, date).quantize(
                Decimal(1) / 10 ** InvoiceLine.unit_price.digits[1]))
        res['monthly_void_premium_excl_tax'] = self.currency.round(
            Tax._reverse_unit_compute(res['monthly_void_premium_incl_tax'],
                self.coverage.taxes, date).quantize(
                Decimal(1) / 10 ** InvoiceLine.unit_price.digits[1]))
        return res

    @classmethod
    def get_premium(cls, options, names, date=None):
        annual_premiums_incl_tax = {o.id: Decimal('0.0') for o in options}
        annual_premiums_excl_tax = {o.id: Decimal('0.0') for o in options}
        annual_premiums_taxes = {o.id: Decimal('0.0') for o in options}
        monthly_premiums_incl_tax = {o.id: Decimal('0.0') for o in options}
        monthly_premiums_excl_tax = {o.id: Decimal('0.0') for o in options}
        monthly_premiums_taxes = {o.id: Decimal('0.0') for o in options}
        InvoiceLine = Pool().get('account.invoice.line')

        date = date or utils.today()
        for option in options:
            premiums = utils.get_good_versions_at_date(option, 'premiums',
                max(date, option.initial_start_date or utils.today()),
                'start', 'end')
            extra_premiums = utils.get_good_versions_at_date(option,
                'extra_premiums',
                max(date, option.initial_start_date or utils.today()),
                'start', 'end')
            annual_premium_incl_tax = annual_premium_excl_tax = \
                monthly_premium_incl_tax = monthly_premium_excl_tax = \
                Decimal('0.0')
            if not premiums:
                void_premiums = option.get_void_premium(
                    option.initial_start_date)
                annual_premium_incl_tax = void_premiums.get(
                    'annual_void_premium_incl_tax')
                monthly_premium_incl_tax = void_premiums.get(
                    'monthly_void_premium_incl_tax')
                annual_premium_excl_tax = void_premiums.get(
                    'annual_void_premium_excl_tax')
                monthly_premium_excl_tax = void_premiums.get(
                    'monthly_void_premium_excl_tax')
            else:
                premiums.sort(key=lambda x: x.start)
                last_premium = premiums[-1]
                Tax = Pool().get('account.tax')
                if last_premium.frequency in ['yearly', 'monthly', 'quaterly',
                        'half_yearly']:
                    annual_premium_incl_tax = option. \
                        compute_premium_with_extra_premium(last_premium.amount,
                            extra_premiums) * Decimal(
                                ANNUAL_CONVERSION_TABLE[last_premium.frequency])
                    annual_premium_excl_tax = option.currency.round(
                        Tax._reverse_unit_compute(annual_premium_incl_tax,
                            last_premium.taxes, date).quantize(
                            Decimal(1) / 10 ** InvoiceLine.unit_price.digits[1])
                            )
                if option.status != 'void' and option.start_date and \
                    option.start_date <= date <= (option.end_date or datetime.
                        date.max):
                    latest_premium = premiums[0]
                    if latest_premium.frequency in ['yearly', 'monthly',
                            'quaterly', 'half_yearly']:
                        monthly_premium_incl_tax = option. \
                            compute_premium_with_extra_premium(
                                latest_premium.amount, extra_premiums) / \
                            Decimal(FREQUENCY_CONVERSION_TABLE[
                                    latest_premium.frequency])
                        monthly_premium_excl_tax = option.currency.round(
                            Tax._reverse_unit_compute(monthly_premium_incl_tax,
                                latest_premium.taxes, date).quantize(
                                Decimal(1)
                                / 10 ** InvoiceLine.unit_price.digits[1]))

            annual_premiums_incl_tax[option.id] = annual_premium_incl_tax
            annual_premiums_excl_tax[option.id] = annual_premium_excl_tax
            annual_premiums_taxes[option.id] = annual_premium_incl_tax - \
                annual_premium_excl_tax
            monthly_premiums_incl_tax[option.id] = monthly_premium_incl_tax
            monthly_premiums_excl_tax[option.id] = monthly_premium_excl_tax
            monthly_premiums_taxes[option.id] = monthly_premium_incl_tax - \
                monthly_premium_excl_tax

        result = {
            'annual_premium_incl_tax': annual_premiums_incl_tax,
            'annual_premium_excl_tax': annual_premiums_excl_tax,
            'annual_taxes': annual_premiums_taxes,
            'monthly_premium_incl_tax': monthly_premiums_incl_tax,
            'monthly_premium_excl_tax': monthly_premiums_excl_tax,
            'monthly_taxes': monthly_premiums_taxes,
            }
        return {key: result[key] for key in names}

    def compute_premium_with_extra_premium(self, amount, extra_premiums):
        premium_amount = amount or Decimal('0.0')
        for extra_premium in extra_premiums:
            premium_amount += sum([x.amount for x in extra_premium.premiums], 0)
        return premium_amount

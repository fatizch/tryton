# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms
import datetime

from collections import defaultdict
from decimal import Decimal

from sql.operators import Concat
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
__metaclass__ = PoolMeta

ANNUAL_CONVERSION_TABLE = {
    'yearly': 1,
    'half_yearly': 2,
    'quaterly': 4,
    'monthly': 12,
    }


class Contract:
    __name__ = 'contract'

    broker = fields.Function(
        fields.Many2One('distribution.network', 'Broker',
            domain=[('party.agents', '!=', None)], states=_STATES,
            depends=_DEPENDS),
        'on_change_with_broker', 'setter_void')
    broker_party = fields.Function(
        fields.Many2One('party.party', 'Broker'),
        'on_change_with_broker_party', searcher='search_broker_party')
    agency = fields.Many2One('distribution.network', 'Agency',
        domain=[If(Bool(Eval('broker', False)),
                ['OR', ('id', '=', Eval('broker')),
                    ('parents', '=', Eval('broker'))],
                [('parent', '=', None)])],
        states={
            'readonly': ((Eval('status') != 'quote') | ~Eval('broker', None)),
            },
        depends=_DEPENDS + ['broker'], ondelete='RESTRICT')
    agent = fields.Many2One('commission.agent', 'Agent', ondelete='RESTRICT',
        domain=[
            ('type_', '=', 'agent'),
            ('plan.commissioned_products', '=', Eval('product')),
            ('party', '=', Eval('broker_party')),
            ['OR',
                ('end_date', '>=', Eval('initial_start_date')),
                ('end_date', '=', None),
                ],
            ['OR',
                ('start_date', '<=', Eval('initial_start_date')),
                ('start_date', '=', None),
                ],
            ],
        states=_STATES, depends=_DEPENDS + ['broker_party', 'product',
            'initial_start_date'])
    insurer_agent_cache = Cache('contract_insurer_agent')

    @classmethod
    def _export_light(cls):
        return (super(Contract, cls)._export_light() |
            set(['agency', 'agent']))

    def get_invoice(self, start, end, billing_information):
        invoice = super(Contract, self).get_invoice(start, end,
            billing_information)
        invoice.agent = self.agent
        return invoice

    def find_insurer_agent_domain(self, coverage=None, line=None):
        domain = [('type_', '=', 'principal')]
        if self.agent and self.agent.plan.insurer_plan:
            domain.append(('plan', '=', self.agent.plan.insurer_plan))
        if not coverage and line and getattr(line, 'details', None):
            coverage = getattr(line.details[0], 'rated_entity', None)
        if coverage and getattr(coverage, 'insurer', None):
            domain.append(('party', '=', coverage.insurer.party))
        else:
            return None
        return domain

    def get_insurer_pattern(self, coverage=None, line=None):
        pattern = {}
        if self.agent and self.agent.plan.insurer_plan:
            pattern['plan'] = self.agent.plan.insurer_plan
        if not coverage and line:
            coverage = getattr(line.details[0], 'rated_entity', None)
        if coverage:
            pattern['coverage'] = coverage
            if coverage.insurer:
                pattern['party'] = coverage.insurer.party
        return pattern

    def find_insurer_agent(self, coverage=None, line=None):
        pool = Pool()
        Agent = pool.get('commission.agent')
        domain = self.find_insurer_agent_domain(coverage, line)
        if not domain:
            return
        agents = Agent.search(domain)
        pattern = self.get_insurer_pattern(coverage, line)
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

    @fields.depends('agent')
    def on_change_with_broker(self, name=None):
        return (self.agent.party.network[0].id
            if self.agent and self.agent.party.network else None)

    @fields.depends('broker')
    def on_change_with_broker_party(self, name=None):
        return self.broker.party.id if self.broker else None

    @fields.depends('broker', 'agent', 'agency', 'product', 'start_date')
    def on_change_broker(self):
        self.broker_party = self.on_change_with_broker_party()
        if self.broker_party:
            self.agent = self.on_change_with_agent()
        if not self.broker:
            self.agency = None

    @fields.depends('broker_party', 'product', 'initial_start_date')
    def on_change_with_agent(self):
        if self.product and self.initial_start_date:
            return utils.auto_complete_with_domain(self, 'agent')

    @classmethod
    def change_broker(cls, contracts, new_broker, at_date,
            update_contracts=False, agency=None, create_missing=False):
        pool = Pool()
        Commission = pool.get('commission')
        Agent = pool.get('commission.agent')
        Event = pool.get('event')
        per_agent = defaultdict(list)
        [per_agent[contract.agent].append(contract) for contract in contracts]

        agent_matches = Agent.find_matches(per_agent.keys(), new_broker)

        to_create = []
        with model.error_manager():
            for src_agent, dest_agent in agent_matches.items():
                if dest_agent:
                    continue
                if not create_missing:
                    Agent.append_functional_error('agent_not_found', (
                            new_broker.rec_name,
                            Agent.format_hash(dict(src_agent.get_hash()))))
                    continue
                to_create.append(src_agent)
        if to_create:
            agent_matches.update({
                    src_agent: src_agent.copy_to_broker(new_broker)
                    for src_agent in to_create})

        for from_agent, to_agent in agent_matches.iteritems():
            if update_contracts:
                cls.write(per_agent[from_agent], {'agent': to_agent.id,
                        'agency': agency})
            Commission.modify_agent(Commission.search([
                        ('commissioned_contract', 'in',
                            per_agent[from_agent]),
                        ('agent', '=', from_agent),
                        ('origin.coverage_start', '>=', at_date,
                            'account.invoice.line')]),
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


class ContractOption:
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
            'annual_void_premium_incl_tax': 0,
            'annual_void_premium_excl_tax': 0,
            'monthly_void_premium_incl_tax': 0,
            'monthly_void_premium_excl_tax': 0,
            }
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
            premiums = utils.get_good_versions_at_date(option, 'premiums', date,
                'start', 'end')
            extra_premiums = utils.get_good_versions_at_date(option,
                'extra_premiums', date, 'start', 'end')
            annual_premium_incl_tax = annual_premium_excl_tax = \
                monthly_premium_incl_tax = monthly_premium_excl_tax = \
                Decimal('0.0')
            if not premiums:
                void_premiums = option.get_void_premium(
                    option.initial_start_date)
                annual_premium_incl_tax = void_premiums.get(
                    'annual_void_premium_incl_tax', 0)
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

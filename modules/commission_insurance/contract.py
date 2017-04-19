# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict
from decimal import Decimal

from sql.operators import Concat
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, If, Bool
from trytond.cache import Cache, freeze

from trytond.modules.coog_core import fields, utils, model
from trytond.modules.contract import _STATES, _DEPENDS

__all__ = [
    'Contract',
    'ContractOption',
    ]
__metaclass__ = PoolMeta


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
                ('end_date', '>=', Eval('start_date')),
                ('end_date', '=', None),
                ],
            ['OR',
                ('start_date', '<=', Eval('start_date')),
                ('start_date', '=', None),
                ],
            ],
        states=_STATES, depends=_DEPENDS + ['broker_party', 'product',
            'start_date'])
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
        if not coverage and line:
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

    @fields.depends('broker_party', 'product', 'start_date')
    def on_change_with_agent(self):
        if self.product and self.start_date:
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

    def compute_premium_with_extra_premium(self, amount, extra_premiums):
        premium_amount = amount or Decimal('0.0')
        for extra_premium in extra_premiums:
            premium_amount += sum([x.amount for x in extra_premium.premiums], 0)
        return premium_amount

from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, If

from trytond.modules.cog_utils import fields
from trytond.modules.contract import _STATES, _DEPENDS

__all__ = [
    'Contract',
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
        fields.Many2One('party.party', 'Broker Party'),
        'on_change_with_broker_party')
    agency = fields.Many2One('distribution.network', 'Agency',
        domain=[('parents', '=', Eval('broker'))],
        states=_STATES, depends=_DEPENDS + ['broker'])
    agent = fields.Many2One('commission.agent', 'Agent', ondelete='RESTRICT',
        domain=[
            ('type_', '=', 'agent'),
            ('plan.commissioned_products', '=', Eval('product')),
            If(~Eval('broker_party'),
                (),
                ('party', '=', Eval('broker_party')),
                ),
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

    @classmethod
    def _export_light(cls):
        return (super(Contract, cls)._export_light() |
            set(['agency', 'agent']))

    def get_invoice(self, start, end, billing_information):
        invoice = super(Contract, self).get_invoice(start, end,
            billing_information)
        invoice.agent = self.agent
        return invoice

    def find_insurer_agent_domain(self, line):
        domain = [('type_', '=', 'principal')]
        if self.agent and self.agent.plan.insurer_plan:
            domain.append(('plan', '=', self.agent.plan.insurer_plan))
        coverage = getattr(line.details[0], 'rated_entity', None)
        if coverage and getattr(coverage, 'insurer', None):
            domain.append(('party', '=', coverage.insurer.party))
        else:
            return None
        return domain

    def get_insurer_pattern(self, line):
        pattern = {}
        if self.agent and self.agent.plan.insurer_plan:
            pattern['plan'] = self.agent.plan.insurer_plan
        coverage = getattr(line.details[0], 'rated_entity', None)
        if coverage:
            pattern['option'] = coverage
            if coverage.insurer:
                pattern['party'] = coverage.insurer.party
        return pattern

    def find_insurer_agent(self, line):
        pool = Pool()
        Agent = pool.get('commission.agent')
        domain = self.find_insurer_agent_domain(line)
        if not domain:
            return
        agents = Agent.search(domain)
        for agent in agents:
            for plan_line in agent.plan.lines:
                if plan_line.match(self.get_insurer_pattern(line)):
                    return agent

    def finalize_invoices_lines(self, lines):
        super(Contract, self).finalize_invoices_lines(lines)
        for line in lines:
            line.principal = self.find_insurer_agent(line)
        return lines

    @fields.depends('agent')
    def on_change_with_broker(self, name=None):
        return (self.agent.party.network[0].id
            if self.agent and self.agent.party.network else None)

    @fields.depends('broker')
    def on_change_with_broker_party(self, name=None):
        return self.broker.party.id if self.broker else None

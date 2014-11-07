from trytond.pool import PoolMeta, Pool

from trytond.modules.cog_utils import fields
from trytond.modules.contract import _STATES, _DEPENDS

__all__ = [
    'Contract',
    ]
__metaclass__ = PoolMeta


class Contract:
    __name__ = 'contract'

    agent = fields.Many2One('commission.agent', 'Agent', ondelete='RESTRICT',
        states=_STATES, depends=_DEPENDS)

    def get_invoice(self, start, end, billing_information):
        invoice = super(Contract, self).get_invoice(start, end,
            billing_information)
        invoice.agent = self.agent
        return invoice

    def find_insurer_agent_domain(self, line):
        domain = [('type_', '=', 'principal')]
        if self.agent and self.agent.plan.plan_relation:
            domain.append(('plan', '=', self.agent.plan.plan_relation[0]))
        coverage = getattr(line.details[0], 'rated_entity', None)
        if coverage and getattr(coverage, 'insurer', None):
            domain.append(('party', '=', coverage.insurer.party))
        else:
            return None
        return domain

    def get_insurer_pattern(self, line):
        pattern = {}
        if self.agent.plan.plan_relation:
            pattern['plan'] = self.agent.plan.plan_relation[0]
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

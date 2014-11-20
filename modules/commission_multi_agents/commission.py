from trytond.pool import PoolMeta
from trytond.modules.cog_utils import fields, model

__all__ = [
    'Agent',
    'Plan',
    'PlanAgentRelation',
    ]
__metaclass__ = PoolMeta


class Agent:
    __name__ = 'commission.agent'

    commissioned_agents = fields.One2Many('commission.agent',
        'commissioned_with_agent', 'Commissioned Agent')
    commissioned_with_agent = fields.Many2One('commission.agent',
        'Commissioned With Agent', ondelete='RESTRICT')

    def fill_commissioned_agents(self):
        agents = []
        for agent in self.plan.commissionned_agents:
            agents.append(agent)
        for agent in self.commissioned_agents:
            agents.append(agent)
            agents.extend(agent.fill_commissioned_agents())
        return agents


class Plan:
    __name__ = 'commission.plan'

    commissionned_agents = fields.Many2Many('commission_plan-agent', 'plan',
        'agent', 'Commissioned Agents')


class PlanAgentRelation(model.CoopSQL, model.CoopView):
    'Commission Plan - Agent'
    __name__ = 'commission_plan-agent'

    plan = fields.Many2One('commission.plan', 'Plan', ondelete='CASCADE')
    agent = fields.Many2One('commission.agent', 'Agent', ondelete='RESTRICT')

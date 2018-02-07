# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

from trytond.modules.coog_core import model, fields

__all__ = [
    'CommissionPlan',
    'CommissionPlanFee',
    'Agent',
    'AgentFee',
    'CreateAgents',
    'CreateAgentsAsk',
    ]


class CommissionPlan:
    __metaclass__ = PoolMeta
    __name__ = 'commission.plan'

    fees = fields.Many2Many('commission.plan-account.fee', 'plan', 'fee',
        'Fees')


class CommissionPlanFee(model.CoogSQL):
    'Commission Plan Fee'

    __name__ = 'commission.plan-account.fee'

    fee = fields.Many2One('account.fee', 'Fee', ondelete='RESTRICT',
        required=True)
    plan = fields.Many2One('commission.plan', 'Plan', ondelete='CASCADE',
        required=True)


class Agent:
    __metaclass__ = PoolMeta
    __name__ = 'commission.agent'

    fees = fields.Many2Many('commission.agent-account.fee', 'agent', 'fee',
        'Fees')


class AgentFee(model.CoogSQL):
    'Agent Fee'

    __name__ = 'commission.agent-account.fee'

    fee = fields.Many2One('account.fee', 'Fee', ondelete='RESTRICT',
        required=True)
    agent = fields.Many2One('commission.agent', 'Agent', ondelete='CASCADE',
        required=True)


class CreateAgents:
    __metaclass__ = PoolMeta
    __name__ = 'commission.create_agents'

    def new_agent(self, party, plan):
        agent = super(CreateAgents, self).new_agent(party, plan)
        agent['fees'] = [('add', [x.id for x in self.ask.fees])]
        return agent

    def agent_update_values(self):
        vals = super(CreateAgents, self).agent_update_values()
        vals['fees'] = [('add', [x.id for x in self.ask.fees])]
        return vals


class CreateAgentsAsk:
    __metaclass__ = PoolMeta
    __name__ = 'commission.create_agents.ask'

    fees = fields.Many2Many('account.fee', None, None, 'Fees')

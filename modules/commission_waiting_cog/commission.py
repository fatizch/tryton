# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelView
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval

from trytond.modules.coog_core import fields

__all__ = [
    'Commission',
    'Agent',
    'CreateAgents',
    'CreateAgentsAsk',
    ]
__metaclass__ = PoolMeta


class Commission:
    __metaclass__ = PoolMeta
    __name__ = 'commission'

    @classmethod
    @ModelView.button
    def create_waiting_move(cls, commissions):
        pool = Pool()
        Move = pool.get('account.move')
        super(Commission, cls).create_waiting_move(commissions)
        moves = [commission.waiting_move for commission in commissions
            if commission.waiting_move]
        Move.post(moves)


class Agent:
    __metaclass__ = PoolMeta
    __name__ = 'commission.agent'

    @classmethod
    def _export_light(cls):
        return (super(Agent, cls)._export_light() | set(['waiting_account']))


class CreateAgents:
    __metaclass__ = PoolMeta
    __name__ = 'commission.create_agents'

    def new_agent(self, party, plan):
        agent = super(CreateAgents, self).new_agent(party, plan)
        agent['waiting_account'] = self.ask.waiting_account
        return agent

    def agent_update_values(self):
        vals = super(CreateAgents, self).agent_update_values()
        vals['waiting_account'] = self.ask.waiting_account
        return vals


class CreateAgentsAsk:
    __metaclass__ = PoolMeta
    __name__ = 'commission.create_agents.ask'

    waiting_account = fields.Many2One('account.account', 'Waiting Account',
        domain=[
            ('company', '=', Eval('company')),
            ('kind', 'in', ['payable', 'other']),
            ],
        depends=['company'], required=True)

from trytond import backend
from trytond.pool import PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction

from trytond.modules.cog_utils import fields, model, coop_string

__all__ = [
    'Agent',
    'AgentAgentRelation',
    'Plan',
    'PlanAgentRelation',
    ]
__metaclass__ = PoolMeta


class Agent:
    __name__ = 'commission.agent'

    second_level_commission = fields.Function(
        fields.Boolean('Second level commission',
            states={'invisible': Eval('type_') != 'agent'},
            depends=['type_']),
        'get_second_level_commission',
        searcher='search_second_level_commission')
    commissioned_agents = fields.Many2Many('commission.agent-agent',
        'from_agent', 'to_second_level_agent', 'Commissioned Agent',
        domain=[
            ('second_level_commission', '=', True),
            ('id', '!=', Eval('id')),
            ],
        states={'invisible': Eval('type_') != 'agent'},
        depends=['type_', 'id'])

    @classmethod
    def __register__(cls, module_name):
        super(Agent, cls).__register__(module_name)
        # Migration from 1.3: Drop commissioned_with_agent column
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().cursor
        agent = TableHandler(cursor, cls)
        if agent.column_exist('commissioned_with_agent'):
            agent.drop_column('commissioned_with_agent')

    @classmethod
    def search_second_level_commission(cls, name, clause):
        return [('plan.second_level_commission',) + tuple(clause[1:])]

    def fill_commissioned_agents(self):
        agents = []
        for agent in self.plan.commissioned_agents:
            agents.append(agent)
        for agent in self.commissioned_agents:
            agents.append(agent)
            agents.extend(agent.fill_commissioned_agents())
        return agents

    def get_second_level_commission(self, name):
        return self.plan.second_level_commission if self.plan else None

    @classmethod
    def format_hash(cls, hash_dict):
        return super(Agent, cls).format_hash(hash_dict) + '\n' + \
            coop_string.translate_label(cls, 'commissioned_agents') + ' : ' + \
            ', '.join([x.rec_name for x in hash_dict['commissioned_agents']])

    def get_hash(self):
        return super(Agent, self).get_hash() + (
            ('commissioned_agents', tuple([x.id
                        for x in self.commissioned_agents])),)


class AgentAgentRelation(model.CoopSQL, model.CoopView):
    'Multi Agent Relation'

    __name__ = 'commission.agent-agent'

    from_agent = fields.Many2One('commission.agent', 'From Agent',
        ondelete='CASCADE')
    to_second_level_agent = fields.Many2One('commission.agent',
        'To Second Level Agent', ondelete='RESTRICT')


class Plan:
    __name__ = 'commission.plan'

    second_level_commission = fields.Boolean('Second level commission',
        states={'invisible': Eval('type_') != 'agent'},
        depends=['type_'])
    commissioned_agents = fields.Many2Many('commission_plan-agent', 'plan',
        'agent', 'Commissioned Agents',
        domain=[('second_level_commission', '=', True)],
        states={'invisible': Eval('type_') != 'agent'},
        depends=['type_'])

    @classmethod
    def _export_light(cls):
        return super(Plan, cls)._export_light() | {'commissioned_agents'}


class PlanAgentRelation(model.CoopSQL, model.CoopView):
    'Commission Plan - Agent'
    __name__ = 'commission_plan-agent'

    plan = fields.Many2One('commission.plan', 'Plan', ondelete='CASCADE')
    agent = fields.Many2One('commission.agent', 'Agent', ondelete='RESTRICT')

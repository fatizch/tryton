# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond import backend
from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.coog_core import fields, model, coog_string

__all__ = [
    'Commission',
    'Agent',
    'AgentAgentRelation',
    'Plan',
    'PlanAgentRelation',
    ]


class Commission:
    __metaclass__ = PoolMeta
    __name__ = 'commission'

    def update_agent_from_contract(self):
        if self.agent.second_level_commission:
            return
        super(Commission, self).update_agent_from_contract()


class Agent:
    __metaclass__ = PoolMeta
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
            ('OR', ('second_level_commission', '=', True),
                ('type_', '!=', 'agent')),
            ('id', '!=', Eval('id')),
            ],
        states={'invisible': Eval('type_') != 'agent'},
        depends=['type_', 'id'])
    from_commission_agents = fields.Many2Many('commission.agent-agent',
        'to_second_level_agent', 'from_agent', 'From Commission Agents',
        readonly=True)
    from_plans = fields.Many2Many('commission_plan-agent', 'agent',
        'plan', 'From Plans', readonly=True)
    childs = fields.Function(
        fields.One2Many('commission.agent', None, 'Childs'),
        'get_childs')
    parents = fields.Function(
        fields.Many2Many('commission.agent', None, None, 'Parents'),
        'get_parents')

    @classmethod
    def __register__(cls, module_name):
        super(Agent, cls).__register__(module_name)
        # Migration from 1.3: Drop commissioned_with_agent column
        TableHandler = backend.get('TableHandler')
        agent = TableHandler(cls)
        if agent.column_exist('commissioned_with_agent'):
            agent.drop_column('commissioned_with_agent')

    @classmethod
    def _export_skips(cls):
        return super(Agent, cls)._export_skips() | {'from_commission_agents',
            'from_plans'}

    @classmethod
    def copy(cls, agents, default=None):
        default = default.copy() if default else {}
        default.setdefault('from_commission_agents', None)
        default.setdefault('from_plans', None)
        return super(Agent, cls).copy(agents, default=default)

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
            coog_string.translate_label(cls, 'commissioned_agents') + ' : ' + \
            ', '.join([x.rec_name for x in hash_dict['commissioned_agents']])

    def get_hash(self):
        return super(Agent, self).get_hash() + (
            ('commissioned_agents', tuple([x.id
                        for x in self.commissioned_agents])),)

    def get_childs(self, name=None):
        return [a.id for a in self.commissioned_agents
            ] + self.plan.get_agent_childs()

    def get_parents(self, name=None):
        return [x.id for x in self.from_plans + self.from_commission_agents]


class AgentAgentRelation(model.CoogSQL, model.CoogView):
    'Multi Agent Relation'

    __name__ = 'commission.agent-agent'

    from_agent = fields.Many2One('commission.agent', 'From Agent',
        ondelete='CASCADE')
    to_second_level_agent = fields.Many2One('commission.agent',
        'To Second Level Agent', ondelete='RESTRICT')


class Plan:
    __metaclass__ = PoolMeta
    __name__ = 'commission.plan'

    second_level_commission = fields.Boolean('Second level commission',
        states={'invisible': Eval('type_') != 'agent'},
        depends=['type_'])
    commissioned_agents = fields.Many2Many('commission_plan-agent', 'plan',
        'agent', 'Commissioned Agents',
        domain=[('OR',
                ('second_level_commission', '=', True),
                ('type_', '!=', 'agent'))],
        states={'invisible': Eval('type_') != 'agent'},
        depends=['type_'])

    @classmethod
    def _export_light(cls):
        return super(Plan, cls)._export_light() | {'commissioned_agents'}

    def get_agent_childs(self):
        res = []
        for agent in self.commissioned_agents:
            res.append(agent.id)
            res += agent.get_childs()
        return res


class PlanAgentRelation(model.CoogSQL, model.CoogView):
    'Commission Plan - Agent'
    __name__ = 'commission_plan-agent'

    plan = fields.Many2One('commission.plan', 'Plan', ondelete='CASCADE')
    agent = fields.Many2One('commission.agent', 'Agent', ondelete='RESTRICT')

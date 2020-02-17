# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

__all__ = [
    'Contract',
    'ContractOption',
    ]


class Contract(metaclass=PoolMeta):
    __name__ = 'contract'

    @classmethod
    def __setup__(cls):
        super(Contract, cls).__setup__()
        cls.agent.domain.append(('second_level_commission', '=', False))
        cls.broker.domain.append(
            ('party.agents.second_level_commission', '=', False))

    def getter_has_prepayment(self, name):
        result = super(Contract, self).getter_has_prepayment(name)
        if self.agent:
            return result or any(x.plan.is_prepayment
                for x in self.agent.commissioned_agents)
        return result

    def _calculate_agents(self):
        agents = super()._calculate_agents()
        if self.agent:
            for agent in self.agent.fill_commissioned_agents():
                if agent not in agents:
                    agents[agent.id] = agent
        return agents


class ContractOption(metaclass=PoolMeta):
    __name__ = 'contract.option'

    def agent_plans_used(self):
        '''
            This method is overrided to handle prepayment
            It's only call when prepayment module is installed
        '''
        used = super(ContractOption, self).agent_plans_used()
        if self.parent_contract.agent:
            sub_agents = self.parent_contract.agent.fill_commissioned_agents()
            for sub_agent in sub_agents:
                used.append((sub_agent, sub_agent.plan))
        return used

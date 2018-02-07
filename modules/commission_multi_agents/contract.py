# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

__all__ = [
    'Contract',
    'ContractOption',
    ]


class Contract:
    __metaclass__ = PoolMeta
    __name__ = 'contract'

    @classmethod
    def __setup__(cls):
        super(Contract, cls).__setup__()
        cls.agent.domain.append(('second_level_commission', '=', False))
        cls.broker.domain.append(
            ('party.agents.second_level_commission', '=', False))


class ContractOption:
    __metaclass__ = PoolMeta
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

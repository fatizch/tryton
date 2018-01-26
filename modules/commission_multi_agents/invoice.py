# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

__all__ = [
    'InvoiceLine',
    ]
__metaclass__ = PoolMeta


class InvoiceLine:
    __metaclass__ = PoolMeta
    __name__ = 'account.invoice.line'

    @property
    def agent_plans_used(self):
        used = super(InvoiceLine, self).agent_plans_used
        if self.invoice.agent:
            sub_agents = self.invoice.agent.fill_commissioned_agents()
            for sub_agent in sub_agents:
                used.append((sub_agent, sub_agent.plan))
        return used

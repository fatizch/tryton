from trytond.pool import PoolMeta

__all__ = [
    'InvoiceLine',
    ]
__metaclass__ = PoolMeta


class InvoiceLine:
    __name__ = 'account.invoice.line'

    @property
    def agent_plans_used(self):
        used = super(InvoiceLine, self).agent_plans_used
        if self.invoice.agent:
            sub_agents = self.invoice.agent.fill_commissioned_agents()
            for sub_agent in sub_agents:
                used.append((sub_agent, sub_agent.plan))
        return used

from trytond.pool import PoolMeta

__metaclass__ = PoolMeta
__all__ = [
    'Contract',
    ]


class Contract:
    __name__ = 'contract'

    def appliable_fees(self):
        all_fees = super(Contract, self).appliable_fees()
        if self.agent:
            all_fees = all_fees | set(self.agent.fees + self.agent.plan.fees)
        return all_fees

from trytond.pool import PoolMeta

__metaclass__ = PoolMeta
__all__ = [
    'Contract',
    ]


class Contract:
    __name__ = 'contract'

    def appliable_fees(self):
        all_fees = super(Contract, self).appliable_fees()
        return all_fees | set(self.agent.plan.fees if self.agent else [])

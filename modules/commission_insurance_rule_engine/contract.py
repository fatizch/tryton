from trytond.pool import PoolMeta

__metaclass__ = PoolMeta
__all__ = [
    'Contract',
    ]


class Contract:
    __name__ = 'contract'

    def get_all_extra_data(self, at_date):
        extra_data = super(Contract, self).get_all_extra_data(at_date)
        if self.agent:
            extra_data.update(self.agent.extra_data or {})
        return extra_data

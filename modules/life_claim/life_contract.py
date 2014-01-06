from trytond.pool import PoolMeta

from trytond.modules.coop_utils import utils

__metaclass__ = PoolMeta
__all__ = [
    'ContractOption',
    ]


class ContractOption:
    __name__ = 'contract.option'

    def is_item_covered(self, loss):
        res = super(ContractOption, self).is_item_covered(loss)
        if not res or not hasattr(loss, 'covered_person'):
            return res
        for covered_data in self.covered_data:
            if not utils.is_effective_at_date(covered_data, loss.start_date):
                continue
            if covered_data.is_party_covered(loss.covered_person,
                    loss.start_date):
                return True
        return False

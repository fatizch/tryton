from trytond.pool import PoolMeta

from trytond.modules.coop_utils import utils

__all__ = [
    'LifeOption',
]


class LifeOption():
    'Option'

    __name__ = 'ins_contract.option'
    __metaclass__ = PoolMeta

    def is_item_covered(self, loss):
        res = super(LifeOption, self).is_item_covered(loss)
        if not res or not hasattr(loss, 'covered_person'):
            return res
        for covered_data in self.covered_data:
            if not utils.is_effective_at_date(covered_data, loss.start_date):
                continue
            if covered_data.is_person_covered(loss.covered_person,
                    loss.start_date):
                return True
        return False

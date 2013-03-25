from trytond.pool import PoolMeta

from trytond.modules.coop_utils import utils

__all__ = [
    'ClaimContract',
    'ClaimOption',
]


class ClaimContract():
    'Contract'

    __name__ = 'ins_contract.contract'
    __metaclass__ = PoolMeta

    def get_possible_benefits(self, at_date, loss_desc, event_desc=None):
        res = {}
        for option in self.get_active_options_at_date(at_date):
            benefits = option.offered.get_possible_benefits(
                loss_desc, event_desc, at_date)
            if benefits:
                res[option.id] = benefits
        return res


class ClaimOption():
    'Option'

    __name__ = 'ins_contract.option'
    __metaclass__ = PoolMeta

    def is_item_covered(self, loss):
        return utils.is_effective_at_date(self, at_date=loss.start_date)

    def get_possible_benefits(self, loss):
        res = []
        if not self.is_item_covered(loss):
            return res
        return self.offered.get_possible_benefits(loss.loss_desc,
            loss.event_desc, loss.start_date)

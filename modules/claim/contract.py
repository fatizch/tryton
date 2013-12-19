from trytond.pool import PoolMeta

from trytond.modules.coop_utils import utils

__metaclass__ = PoolMeta
__all__ = [
    'Contract',
    'Option',
    ]


class Contract:
    __name__ = 'contract'

    def get_possible_benefits(self, loss):
        res = []
        for option in self.options:
            res.extend(option.get_possible_benefits(loss))
        return list(set(res))


class Option:
    __name__ = 'contract.option'

    def is_item_covered(self, loss):
        return utils.is_effective_at_date(self, at_date=loss.start_date)

    def get_possible_benefits(self, loss):
        res = []
        if not self.is_item_covered(loss):
            return res
        return self.offered.get_possible_benefits(loss.loss_desc,
            loss.event_desc, loss.start_date)

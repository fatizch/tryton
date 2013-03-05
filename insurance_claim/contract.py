from trytond.pool import PoolMeta

__all__ = [
    'ClaimContract',
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

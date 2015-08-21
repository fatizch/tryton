from trytond.pool import PoolMeta

from trytond.modules.cog_utils import utils

__metaclass__ = PoolMeta
__all__ = [
    'OptionDescription',
    ]


class OptionDescription:
    __name__ = 'offered.option.description'

    def get_possible_benefits(self, loss_desc=None, event_desc=None,
            at_date=None):
        res = []
        benefits = utils.get_good_versions_at_date(self, 'benefits', at_date)
        for benefit in benefits:
            if not loss_desc or loss_desc in benefit.loss_descs:
                res.append(benefit)
        return res

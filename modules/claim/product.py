from trytond.pool import PoolMeta

from trytond.modules.coop_utils import utils

__al__ = [
    'ClaimCoverage',
]


class ClaimCoverage():
    'Coverage'

    __name__ = 'offered.coverage'
    __metaclass__ = PoolMeta

    def get_possible_benefits(self, loss_desc=None, event_desc=None,
            at_date=None):
        #ToDo replace this method with give_me_benefits
        #and complementary data
        res = []
        benefits = utils.get_good_versions_at_date(self, 'benefits', at_date)
        for benefit in benefits:
            if not loss_desc or loss_desc in benefit.loss_descs:
                res.append(benefit)
        return res

import copy

from trytond.pool import PoolMeta
from trytond.modules.coop_utils import utils

__all__ = ['HealthCoverage']


class HealthCoverage():
    'Coverage'

    __name__ = 'offered.coverage'
    __metaclass__ = PoolMeta

    @classmethod
    def __setup__(cls):
        super(HealthCoverage, cls).__setup__()
        cls.family = copy.copy(cls.family)
        if not cls.family.selection:
            cls.family.selection = []
        utils.append_inexisting(cls.family.selection,
            ('health', 'Health'))

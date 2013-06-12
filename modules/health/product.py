import copy

from trytond.pool import PoolMeta
from trytond.modules.coop_utils import utils, fields

__all__ = [
    'Product',
    'Coverage',
    ]


class Product():
    'Product'

    __name__ = 'offered.product'
    __metaclass__ = PoolMeta

    is_health = fields.Function(
        fields.Boolean('Is Health', states={'invisible': True}),
        'get_is_health_product')

    def get_is_health_product(self, name):
        for coverage in self.coverages:
            if coverage.is_health:
                return True
        return False


class Coverage():
    'Coverage'

    __name__ = 'offered.coverage'
    __metaclass__ = PoolMeta

    is_health = fields.Function(
        fields.Boolean('Is Health', states={'invisible': True}),
        'get_is_health_coverage')

    @classmethod
    def __setup__(cls):
        super(Coverage, cls).__setup__()
        cls.family = copy.copy(cls.family)
        if not cls.family.selection:
            cls.family.selection = []
        utils.append_inexisting(cls.family.selection,
            ('health', 'Health'))

    def get_is_health_coverage(self, name):
        return self.family == 'health'

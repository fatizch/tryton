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
        'get_is_health_product', searcher='search_is_health')

    def get_is_health_product(self, name):
        for coverage in self.coverages:
            if coverage.is_health:
                return True
        return False

    @classmethod
    def search_is_health(cls, name, clause):
        return [('coverages.is_health',) + tuple(clause[1:])]


class Coverage():
    'Coverage'

    __name__ = 'offered.option.description'
    __metaclass__ = PoolMeta

    is_health = fields.Function(
        fields.Boolean('Is Health', states={'invisible': True}),
        'get_is_health_coverage', searcher='search_is_health')

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

    @classmethod
    def search_is_health(cls, name, clause):
        if clause[2] == True:
            return [('family', '=', 'health')]
        else:
            return [('family', '!=', 'health')]

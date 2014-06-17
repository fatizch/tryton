from trytond.pool import PoolMeta
from trytond.modules.cog_utils import fields

__metaclass__ = PoolMeta
__all__ = [
    'Product',
    'OptionDescription',
    ]


class Product:
    __name__ = 'offered.product'

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


class OptionDescription:
    __name__ = 'offered.option.description'

    is_health = fields.Function(
        fields.Boolean('Is Health', states={'invisible': True}),
        'get_is_health_coverage', searcher='search_is_health')

    @classmethod
    def __setup__(cls):
        super(OptionDescription, cls).__setup__()
        cls.family.selection.append(('health', 'Health'))

    def get_is_health_coverage(self, name):
        return self.family == 'health'

    @classmethod
    def search_is_health(cls, name, clause):
        if clause[2] == True:
            return [('family', '=', 'health')]
        else:
            return [('family', '!=', 'health')]

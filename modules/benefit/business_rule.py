import copy

from trytond.pool import PoolMeta

__metaclass__ = PoolMeta
__all__ = [
    'BusinessRuleRoot',
    ]


class BusinessRuleRoot:
    __name__ = 'offered.business_rule_root'

    @classmethod
    def __setup__(cls):
        super(BusinessRuleRoot, cls).__setup__()
        cls.offered = copy.copy(cls.offered)
        cls.offered.selection.append(('benefit', 'Benefit'))

import copy
from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.coop_utils import fields

__all__ = [
    'Contract',
    'Option',
    'CoveredElement',
    ]


class Contract():
    'Contract'

    __name__ = 'contract.contract'
    __metaclass__ = PoolMeta

    is_health = fields.Function(
        fields.Boolean('Is Health', states={'invisible': True}),
        'get_is_health')

    def get_is_health(self, name):
        if not self.options and self.offered:
            return self.offered.is_health
        for option in self.options:
            if option.is_health:
                return True
        return False


class Option():
    'Option'

    __name__ = 'contract.subscribed_option'
    __metaclass__ = PoolMeta

    is_health = fields.Function(
        fields.Boolean('Is Health', states={'invisible': True}),
        'get_is_health')

    def get_is_health(self, name=None):
        return self.offered and self.offered.is_health


class CoveredElement():
    'Covered Element'

    __name__ = 'ins_contract.covered_element'
    __metaclass__ = PoolMeta

    @classmethod
    def __setup__(cls):
        super(CoveredElement, cls).__setup__()
        cls.party = copy.copy(cls.party)
        if not cls.party.context:
            cls.party.context = {}
        cls.party.context['is_health'] = Eval('_parent_contract',
            {}).get('is_health')

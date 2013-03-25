from trytond.pool import PoolMeta
from trytond.pyson import Eval
from trytond.modules.coop_utils import utils

__all__ = [
    'GroupCoveredElement',
]


class GroupCoveredElement():
    'Covered Element'

    __name__ = 'ins_contract.covered_element'
    __metaclass__ = PoolMeta

    @classmethod
    def __setup__(cls):
        super(GroupCoveredElement, cls).__setup__()
        utils.update_states(cls, 'name',
            {'invisible': Eval('_parent_contract', {}).get('kind') != 'group'})
        utils.update_states(cls, 'person',
            {'invisible': Eval('_parent_contract', {}).get('kind') == 'group'})

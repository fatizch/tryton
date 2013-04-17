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

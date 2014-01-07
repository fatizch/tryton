from trytond.pool import PoolMeta
from trytond.modules.coop_utils import utils

__metaclass__ = PoolMeta
__all__ = ['Coverage']


class Coverage:
    __name__ = 'offered.option.description'

    @classmethod
    def __setup__(cls):
        super(Coverage, cls).__setup__()
        utils.update_selection(cls, 'selection', (
                ('pc', 'Property & Casualty'),))

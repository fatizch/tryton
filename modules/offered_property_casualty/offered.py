from trytond.pool import PoolMeta
from trytond.modules.cog_utils import utils

__metaclass__ = PoolMeta
__all__ = ['OptionDescription']


class OptionDescription:
    __name__ = 'offered.option.description'

    @classmethod
    def __setup__(cls):
        super(OptionDescription, cls).__setup__()
        utils.update_selection(cls, 'family', [
                ('pc', 'Property & Casualty')])

from trytond.pool import PoolMeta

from trytond.modules.cog_utils import utils

__metaclass__ = PoolMeta

__all__ = [
    'Clause',
    ]


class Clause:
    __name__ = 'clause'

    @classmethod
    def __setup__(cls):
        super(Clause, cls).__setup__()
        utils.update_selection(cls, 'kind', [('beneficiary', 'Beneficiary')])

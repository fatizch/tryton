import copy
from trytond.pool import PoolMeta

from trytond.pyson import If, Eval
from trytond.modules.coop_utils import utils


__all__ = [
    'Contract',
]


class Contract():
    'Contract'

    __metaclass__ = PoolMeta
    __name__ = 'contract.contract'

    @classmethod
    def __setup__(cls):
        super(Contract, cls).__setup__()
        utils.update_domain(cls, 'receivable_lines', [
            If(~Eval('display_all_lines'), ('payment_amount', '!=', 0), ())])

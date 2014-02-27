from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.cog_utils import fields

__metaclass__ = PoolMeta
__all__ = [
    'ContractClause',
    ]


class ContractClause:
    __name__ = 'contract.clause'

    covered_data = fields.Many2One('contract.covered_data', 'Covered Data',
        ondelete='CASCADE', states={'invisible': ~Eval('covered_data')})

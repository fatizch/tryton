from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.cog_utils import fields

__metaclass__ = PoolMeta

__all__ = [
    'Contract',
    ]


class Contract:
    __name__ = 'contract'

    clauses = fields.One2Many('contract.clause', 'contract', 'Clauses',
        context={'start_date': Eval('start_date')},
        domain=[['OR',
                [('clause', '=', None)],
                [('clause.products', '=', Eval('product'))],
                ]], depends=['product'])

# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.coog_core import fields

__metaclass__ = PoolMeta

__all__ = [
    'Contract',
    ]


class Contract:
    __name__ = 'contract'

    clauses = fields.One2Many('contract.clause', 'contract', 'Clauses',
        context={'start_date': Eval('start_date')},
        domain=['OR',
            [('clause', '=', None)],
            [('clause.products', '=', Eval('product'))],
            ],
        states={'readonly': Eval('status') != 'quote'},
        depends=['product', 'status'], delete_missing=True)

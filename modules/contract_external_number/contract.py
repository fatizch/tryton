# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.coog_core import fields
from trytond.model import Unique

__metaclass__ = PoolMeta

__all__ = [
    'Contract',
    ]


class Contract:
    __metaclass__ = PoolMeta
    __name__ = 'contract'

    external_number = fields.Char('External Number',
        states={'readonly': Eval('status') != 'quote'},
        depends=['status'])

    @classmethod
    def __setup__(cls):
        super(Contract, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('external_number_unique', Unique(t, t.external_number),
                'The external number must be unique'),
            ]

    @classmethod
    def copy(cls, contracts, default=None):
        default = default.copy() if default else {}
        default.setdefault('external_number', None)
        return super(Contract, cls).copy(contracts, default=default)

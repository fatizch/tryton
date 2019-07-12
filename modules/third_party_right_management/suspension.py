# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import PoolMeta


__all__ = [
    'ContractRightSuspension',
    ]


class ContractRightSuspension(metaclass=PoolMeta):
    __name__ = 'contract.right_suspension'

    @classmethod
    def __setup__(cls):
        super(ContractRightSuspension, cls).__setup__()
        cls.end_date.readonly = True

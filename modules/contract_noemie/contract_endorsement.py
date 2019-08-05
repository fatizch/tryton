# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import PoolMeta

__all__ = [
    'Contract',
    ]


class Contract(metaclass=PoolMeta):
    __name__ = 'contract'

    @classmethod
    def _calculate_methods_after_endorsement(cls):
        return super(Contract, cls
            )._calculate_methods_after_endorsement() | {
                'compute_noemie_dates'}

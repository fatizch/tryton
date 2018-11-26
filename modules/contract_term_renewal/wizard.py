# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

__all__ = [
    'TerminateContract',
    ]


class TerminateContract(metaclass=PoolMeta):
    __name__ = 'endorsement.contract.terminate'

    def endorsement_values(self):
        values = super(TerminateContract, self).endorsement_values()
        values['final_renewal'] = True
        return values

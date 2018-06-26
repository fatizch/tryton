# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta


__all__ = [
    'Process',
    ]


class Process:
    __metaclass__ = PoolMeta
    __name__ = 'process'

    @classmethod
    def __setup__(cls):
        super(Process, cls).__setup__()
        cls.kind.selection.append(('prest_ij_treatment',
                'PrestIJ Period Treatment'))

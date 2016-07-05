# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta


__metaclass__ = PoolMeta

__all__ = [
    'ExtraData',
    ]


class ExtraData:
    __name__ = 'extra_data'

    @classmethod
    def __setup__(cls):
        super(ExtraData, cls).__setup__()
        cls.kind.selection.append(('loan', 'Loan'))

# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

__metaclass__ = PoolMeta
__all__ = [
    'Benefit',
    ]


class Benefit:
    __name__ = 'benefit'

    @classmethod
    def get_beneficiary_kind(cls):
        res = super(Benefit, cls).get_beneficiary_kind()
        res.append(['affiliated', 'Affiliated'])
        return res

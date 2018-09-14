# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

__all__ = [
    'Insurer',
    ]


class Insurer:
    __metaclass__ = PoolMeta
    __name__ = 'insurer'

    @classmethod
    def get_insurers_waiting_accounts(cls, insurers, notice_kind):
        result = super(Insurer, cls).get_insurers_waiting_accounts(
            insurers, notice_kind)
        if notice_kind not in ('all', 'benefits'):
            return result
        for insurer in insurers:
            benefit_accounts = {x.waiting_account for x in insurer.benefits
                if x.waiting_account}
            if benefit_accounts:
                result[insurer] = benefit_accounts | result.get(insurer, set())
        return result

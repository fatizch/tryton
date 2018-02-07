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
        if notice_kind == 'benefits':
            return list({(i, benefit.waiting_account) for i in insurers
                    for benefit in i.benefits if benefit.waiting_account})
        return super(Insurer, cls).get_insurers_waiting_accounts(
            insurers, notice_kind)

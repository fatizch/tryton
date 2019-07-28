# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

__all__ = [
    'ThirdPartyPeriod'
    ]


class ThirdPartyPeriod(metaclass=PoolMeta):
    __name__ = 'contract.option.third_party_period'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.start_date.domain = []
        cls.end_date.domain = []

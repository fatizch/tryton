# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

__all__ = [
    'Country',
    ]


class Country:
    __metaclass__ = PoolMeta
    __name__ = 'country.country'

    @classmethod
    def __setup__(cls):
        super(Country, cls).__setup__()
        cls.code.required = True

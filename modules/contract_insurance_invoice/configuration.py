# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.modules.coog_core import fields
from trytond.cache import Cache

__metaclass__ = PoolMeta
__all__ = [
    'OfferedConfiguration',
    ]


class OfferedConfiguration:
    __name__ = 'offered.configuration'

    prorate_premiums = fields.Boolean('Prorate Premiums', help='If checked, '
        'the invoiced amount for a given period is the premium prorated by '
        'the period duration if the period is smaller than the frequency. '
        'If unchecked the invoiced amount is the whole premium.')
    _prorate_cache = Cache('prorate')

    @staticmethod
    def default_prorate_premiums():
        return True

    @classmethod
    def get_cached_prorate_premiums(cls):
        prorate = cls._prorate_cache.get('prorate', default=None)
        if prorate is None:
            config = Pool().get(cls.__name__)(1)
            prorate = config.prorate_premiums
            cls._prorate_cache.set('prorate', prorate)
        return prorate

# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

__all__ = [
    'GlobalSearchSet',
    ]


class GlobalSearchSet:
    __name__ = 'global_search.set'
    __metaclass__ = PoolMeta

    @classmethod
    def global_search_list(cls):
        res = super(GlobalSearchSet, cls).global_search_list()
        res.add('offered.product')
        return res

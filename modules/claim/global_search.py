# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta


__all__ = [
    'GlobalSearchSet'
    ]


class GlobalSearchSet:
    __metaclass__ = PoolMeta
    __name__ = 'global_search.set'

    @classmethod
    def global_search_list(cls):
        result = super(GlobalSearchSet, cls).global_search_list()
        result.add('claim')
        return result

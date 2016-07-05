# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

__all__ = [
    'TestCaseModel',
    ]

__metaclass__ = PoolMeta


class TestCaseModel:
    'Test Case Model'

    __name__ = 'ir.test_case'

    @classmethod
    def global_search_list(cls):
        res = super(TestCaseModel, cls).global_search_list()
        res.add('offered.product')
        return res

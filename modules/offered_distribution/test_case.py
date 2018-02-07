# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

__all__ = [
    'TestCaseModel',
    ]


class TestCaseModel:
    __name__ = 'ir.test_case'
    __metaclass__ = PoolMeta

    @classmethod
    def create_distribution_network(cls, **kwargs):
        if 'company' not in kwargs:
            kwargs['company'] = cls.get_company()
        return super(TestCaseModel, cls).create_distribution_network(**kwargs)

# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta


MODULE_NAME = 'offered'

__all__ = [
    'TestCaseModel',
    ]


class TestCaseModel:
    __metaclass__ = PoolMeta
    __name__ = 'ir.test_case'

    @classmethod
    def get_user_group_dict(cls):
        user_group_dict = super(TestCaseModel, cls).get_user_group_dict()
        user_group_dict['product'].append('offered.group_product_manage')
        return user_group_dict

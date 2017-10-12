# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta


MODULE_NAME = 'commission_insurance'

__all__ = [
    'TestCaseModel',
    ]


class TestCaseModel:
    __metaclass__ = PoolMeta
    __name__ = 'ir.test_case'

    @classmethod
    def get_user_group_dict(cls):
        user_group_dict = super(TestCaseModel, cls).get_user_group_dict()
        user_group_dict['financial'].append(
            'commission_insurance.group_commission_read')
        user_group_dict['commission'].append(
            'commission_insurance.group_commission_manage')
        return user_group_dict

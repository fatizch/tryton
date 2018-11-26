# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta


MODULE_NAME = 'task_manager'

__all__ = [
    'TestCaseModel',
    ]


class TestCaseModel(metaclass=PoolMeta):
    __name__ = 'ir.test_case'

    @classmethod
    def get_user_group_dict(cls):
        user_group_dict = super(TestCaseModel, cls).get_user_group_dict()
        for user_manage in ['financial', 'consultation', 'contract',
                'underwriting', 'claim', 'commission']:
            user_group_dict[user_manage].append('task_manager.group_task_read')
        user_group_dict['product'].append('task_manager.group_task_manage')
        return user_group_dict

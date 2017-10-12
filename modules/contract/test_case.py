# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta


MODULE_NAME = 'contract'

__all__ = [
    'TestCaseModel',
    ]


class TestCaseModel:
    __metaclass__ = PoolMeta
    __name__ = 'ir.test_case'

    @classmethod
    def get_user_group_dict(cls):
        user_group_dict = super(TestCaseModel, cls).get_user_group_dict()
        for user_read in ['consultation', 'financial', 'claim', 'commission']:
            user_group_dict[user_read].append('contract.group_contract_read')
        for user_manage in ['underwriting', 'contract']:
            user_group_dict[user_manage].append(
                'contract.group_contract_manage')
        return user_group_dict

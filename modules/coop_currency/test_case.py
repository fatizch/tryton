from trytond.pool import PoolMeta

from trytond.modules.coop_utils import fields

__all__ = [
    'TestCaseModel',
]

__metaclass__ = PoolMeta


class TestCaseModel:
    'Test Case Model'

    __name__ = 'coop_utils.test_case_model'

    currency = fields.Many2One('currency.currency', 'Main Currency')

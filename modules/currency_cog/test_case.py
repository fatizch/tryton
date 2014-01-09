from trytond.pool import PoolMeta

from trytond.modules.coop_utils import fields

__metaclass__ = PoolMeta
__all__ = [
    'TestCaseModel',
    ]


class TestCaseModel:
    __name__ = 'ir.test_case'

    currency = fields.Many2One('currency.currency', 'Main Currency')

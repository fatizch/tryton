from trytond.pool import PoolMeta

__metaclass__ = PoolMeta
__all__ = [
    'TestCaseModel',
    ]


class TestCaseModel:
    __name__ = 'ir.test_case'

    @classmethod
    def global_search_list(cls):
        result = super(TestCaseModel, cls).global_search_list()
        result.add('contract')
        return result

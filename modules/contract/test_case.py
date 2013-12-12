from trytond.pool import PoolMeta

__all__ = [
    'TestCaseModel',
    ]


class TestCaseModel():
    'Test Case Model'

    __metaclass__ = PoolMeta
    __name__ = 'coop_utils.test_case_model'

    @classmethod
    def global_search_list(cls):
        result = super(TestCaseModel, cls).global_search_list()
        result.add('contract')
        return result

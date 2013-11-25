from trytond.pool import PoolMeta

__all__ = [
    'TestCaseModel',
    ]

__metaclass__ = PoolMeta


class TestCaseModel:
    'Test Case Model'

    __name__ = 'coop_utils.test_case_model'

    @classmethod
    def global_search_list(cls):
        res = super(TestCaseModel, cls).global_search_list()
        res.add('offered.product')
        return res

from trytond.pool import PoolMeta

__all__ = [
    'TestCaseModel',
    ]


class TestCaseModel():
    'Test Case Model'

    __metaclass__ = PoolMeta
    __name__ = 'coop_utils.test_case_model'

    @classmethod
    def create_distribution_network(cls, name, children_name=None,
            children_number=None):
        result = super(TestCaseModel, cls).create_distribution_network(name,
            children_name, children_number)
        result.company = cls.get_company()
        return result

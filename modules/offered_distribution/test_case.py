from trytond.pool import PoolMeta

__metaclass__ = PoolMeta
__all__ = [
    'TestCaseModel',
    ]


class TestCaseModel:
    __name__ = 'ir.test_case'

    @classmethod
    def create_distribution_network(cls, name, children_name=None,
            children_number=None):
        result = super(TestCaseModel, cls).create_distribution_network(name,
            children_name, children_number)
        result.company = cls.get_company()
        return result

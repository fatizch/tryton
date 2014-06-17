from trytond.pool import PoolMeta

__metaclass__ = PoolMeta
__all__ = [
    'TestCaseModel',
    ]


class TestCaseModel:
    __name__ = 'ir.test_case'

    @classmethod
    def create_distribution_network(cls, **kwargs):
        if 'company' not in kwargs:
            kwargs['company'] = cls.get_company()
        return super(TestCaseModel, cls).create_distribution_network(**kwargs)

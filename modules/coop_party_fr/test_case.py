import random

from trytond.pool import PoolMeta

__all__ = [
    'TestCaseModel',
    ]


class TestCaseModel():
    'Test Case Model'

    __metaclass__ = PoolMeta
    __name__ = 'ir.test_case'

    @classmethod
    def create_person(cls, sex='male'):
        result = super(TestCaseModel, cls).create_person(sex)
        if result.gender == 'male':
            ssn = '1'
        elif result.gender == 'female':
            ssn = '2'
        else:
            return result
        ssn = (ssn
            + result.birth_date.strftime('%y%m')
            + str(random.randint(1, 95)).zfill(2)
            + str(random.randint(1, 999)).zfill(3)
            + str(random.randint(1, 999)).zfill(3))
        key = str(97 - int(ssn) % 97).zfill(2)
        result.ssn = ssn + key
        return result

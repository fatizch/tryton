# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import random

from trytond.pool import PoolMeta

__metaclass__ = PoolMeta
__all__ = [
    'TestCaseModel',
    ]


class TestCaseModel:
    __name__ = 'ir.test_case'
    __metaclass__ = PoolMeta

    @classmethod
    def new_person(cls, sex='male', with_address=True):
        result = super(TestCaseModel, cls).new_person(sex, with_address)
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

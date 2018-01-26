# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool


MODULE_NAME = 'offered_life_clause'

__metaclass__ = PoolMeta
__all__ = [
    'TestCaseModel',
    ]


class TestCaseModel:
    __name__ = 'ir.test_case'
    __metaclass__ = PoolMeta

    @classmethod
    def beneficiary_clause_test_case(cls):
        Clause = Pool().get('clause')
        cls.load_resources(MODULE_NAME)
        cls.read_csv_file('beneficiary_clause_examples.csv', MODULE_NAME)
        result = []
        for line in cls._loaded_resources[MODULE_NAME]['files'][
                'beneficiary_clause_examples.csv']:
            result.append(cls.create_clause(
                    name=line[0].decode('utf8'),
                    content=line[1].decode('utf8'),
                    kind='beneficiary'))
        Clause.create([x._save_values for x in result])

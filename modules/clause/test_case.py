# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.modules.coog_core import coog_string

MODULE_NAME = 'clause'

__all__ = [
    'TestCaseModel',
    ]


class TestCaseModel:
    __name__ = 'ir.test_case'
    __metaclass__ = PoolMeta

    @classmethod
    def create_clause(cls, **kwargs):
        Clause = Pool().get('clause')
        if 'code' not in kwargs:
            kwargs['code'] = coog_string.slugify(kwargs['name'])
        if 'customizable' not in kwargs:
            kwargs['customizable'] = True
        return Clause(**kwargs)

    @classmethod
    def clause_test_case(cls):
        Clause = Pool().get('clause')
        cls.load_resources(MODULE_NAME)
        cls.read_csv_file('clause_examples.csv', MODULE_NAME)
        result = []
        for line in cls._loaded_resources[MODULE_NAME]['files'][
                'clause_examples.csv']:
            result.append(cls.create_clause(
                    name=line[0].decode('utf8'),
                    content=line[1].decode('utf8')))
        Clause.create([x._save_values for x in result])

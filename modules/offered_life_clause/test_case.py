from trytond.pool import PoolMeta


MODULE_NAME = 'offered_life_clause'

__metaclass__ = PoolMeta
__all__ = [
    'TestCaseModel',
    ]


class TestCaseModel:
    __name__ = 'ir.test_case'

    @classmethod
    def _get_test_case_dependencies(cls):
        result = super(TestCaseModel, cls)._get_test_case_dependencies()
        result['beneficiary_clause_test_case'] = {
            'name': 'Beneficiary Clause Test Case',
            'dependencies': set([]),
            }
        return result

    @classmethod
    def beneficiary_clause_test_case(cls):
        cls.load_resources(MODULE_NAME)
        cls.read_csv_file('beneficiary_clause_examples.csv', MODULE_NAME)
        result = []
        for line in cls._loaded_resources[MODULE_NAME]['files'][
                'beneficiary_clause_examples.csv']:
            result.append(cls.create_clause_from_line(line,
                    kind='beneficiary'))
        return result

from trytond.pool import PoolMeta, Pool
from trytond.modules.cog_utils import coop_string

MODULE_NAME = 'offered_clause'

__metaclass__ = PoolMeta
__all__ = [
    'TestCaseModel',
    ]


class TestCaseModel:
    __name__ = 'ir.test_case'

    @classmethod
    def _get_test_case_dependencies(cls):
        result = super(TestCaseModel, cls)._get_test_case_dependencies()
        result['clause_test_case'] = {
            'name': 'Clause Test Case',
            'dependencies': set(),
            }
        return result

    @classmethod
    def create_clause_from_line(cls, name, content, kind=''):
        pool = Pool()
        Clause = pool.get('clause')
        clause = Clause(name=name, kind=kind, content=content,
            code=coop_string.remove_blank_and_invalid_char(
                name), customizable=True)
        return clause

    @classmethod
    def clause_test_case(cls):
        cls.load_resources(MODULE_NAME)
        cls.read_csv_file('clause_examples.csv', MODULE_NAME)
        result = []
        for line in cls._loaded_resources[MODULE_NAME]['files'][
                'clause_examples.csv']:
            result.append(cls.create_clause_from_line(line[0].decode('utf8'),
                line[1].decode('utf8')))
        return result

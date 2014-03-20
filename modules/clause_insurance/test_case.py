import datetime

from trytond.pool import PoolMeta, Pool
from trytond.modules.cog_utils import coop_string


MODULE_NAME = 'clause_insurance'

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
            'dependencies': set([]),
        }
        return result

    @classmethod
    def create_clause_from_line(cls, line, kind=''):
        pool = Pool()
        Clause = pool.get('clause')
        Version = pool.get('clause.version')
        clause = Clause(name=line[0], title=line[0], kind=kind,
            code=coop_string.remove_blank_and_invalid_char(
                line[0].decode('utf8')), customizable=True)
        clause.versions = [Version(content=line[1],
                start_date=datetime.date(1900, 1, 1))]
        return clause

    @classmethod
    def clause_test_case(cls):
        cls.load_resources(MODULE_NAME)
        cls.read_csv_file('clause_examples.csv', MODULE_NAME)
        result = []
        for line in cls._loaded_resources[MODULE_NAME]['files'][
                'clause_examples.csv']:
            result.append(cls.create_clause_from_line(line))
        return result

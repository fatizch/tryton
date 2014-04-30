from trytond.pool import PoolMeta, Pool
from trytond.modules.cog_utils import coop_string

MODULE_NAME = 'offered_life'

__metaclass__ = PoolMeta
__all__ = [
    'TestCaseModel',
    ]


class TestCaseModel:
    __name__ = 'ir.test_case'

    @classmethod
    def _get_test_case_dependencies(cls):
        result = super(TestCaseModel, cls)._get_test_case_dependencies()
        result['shared_extra_data_test_case'] = {
            'name': 'Shared Complementary Data Test Case',
            'dependencies': set([]),
            }
        result['ceiling_rule_test_case'] = {
            'name': 'Ceiling Rule Test Case',
            'dependencies': set(['table_test_case']),
            }
        result['salary_range_test_case'] = {
            'name': 'Salary Range Test Case',
            'dependencies': set(['ceiling_rule_test_case']),
            }
        return result

    @classmethod
    def get_or_create_extra_data(cls, name, string=None, type_=None,
            kind=None, selection=None):
        ComplementaryData = Pool().get('extra_data')
        schema_el = ComplementaryData()
        schema_el.name = name
        schema_el.string = string
        schema_el.type_ = type_
        schema_el.kind = kind
        schema_el.selection = selection
        return schema_el

    @classmethod
    def shared_extra_data_test_case(cls):
        translater = cls.get_translater(MODULE_NAME)
        schemas = []
        schemas.append(cls.get_or_create_extra_data('is_vip',
                translater('Is VIP'), 'boolean', 'contract'))
        schemas.append(cls.get_or_create_extra_data('salary',
                translater('Annual Salary'), 'numeric', 'sub_elem'))
        schemas.append(cls.get_or_create_extra_data('CSP',
                translater('CSP'), 'selection', 'sub_elem', '\n'.join([
                                'CSP1: CSP1', 'CSP2: CSP2', 'CSP3: CSP3',
                                'CSP4: CSP4'])))
        return schemas

    @classmethod
    def create_rule(cls, name, code, tables=None):
        RuleEngine = Pool().get('rule_engine')
        Table = Pool().get('table')
        Context = Pool().get('rule_engine.context')
        existing = RuleEngine.search([('name', '=', name)])
        if existing:
            return existing[0]
        if not tables:
            tables = []
        rule = RuleEngine()
        rule.name = name
        rule.short_name = coop_string.remove_blank_and_invalid_char(name)
        rule.algorithm = code
        rule.parameters = []
        rule.context = Context(1)
        rule.tables_used = Table.search([('code', 'in', tables)])
        return rule

    @classmethod
    def ceiling_rule_test_case(cls):
        rules = []
        for (name, factor) in [('Plafond TA', 1), ('Plafond TB', 4),
                    ('Plafond TC', 8), ('Plafond T2', 3)]:
            rules.append(cls.create_rule(name,
                    'PMSS = table_PMSS(date_de_calcul())\n'
                    'return %s * PMSS' % factor,
                    tables=['PMSS']))
        return rules

    @classmethod
    def create_salary_range(cls, code, floor_name=None, ceiling_name=None):
        pool = Pool()
        SalaryRange = pool.get('salary_range')
        SalaryRangeVersion = pool.get('salary_range.version')
        Rule = pool.get('rule_engine')
        salary_range = SalaryRange()
        salary_range.code = code
        version = SalaryRangeVersion()
        if floor_name:
            version.floor = Rule.search([('name', '=', floor_name)])[0]
        if ceiling_name:
            version.floor = Rule.search([('name', '=', ceiling_name)])[0]
        salary_range.versions = [version]
        return salary_range

    @classmethod
    def salary_range_test_case(cls):
        result = []
        result.append(cls.create_salary_range('TA', ceiling_name='Plafond TA'))
        result.append(cls.create_salary_range('TB', floor_name='Plafond TA',
                ceiling_name='Plafond TB'))
        result.append(cls.create_salary_range('TC', floor_name='Plafond TB',
                ceiling_name='Plafond TC'))
        result.append(cls.create_salary_range('TD', floor_name='Plafond TC'))
        result.append(cls.create_salary_range('T1', ceiling_name='Plafond TA'))
        result.append(cls.create_salary_range('T2', floor_name='Plafond TA',
                ceiling_name='Plafond T2'))
        return result

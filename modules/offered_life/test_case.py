# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
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
            'name': 'Shared Extra Data Test Case',
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
    def create_extra_data(cls, **kwargs):
        ExtraData = Pool().get('extra_data')
        return ExtraData(**kwargs)

    @classmethod
    def extra_data_test_case(cls):
        ExtraData = Pool().get('extra_data')
        translater = cls.get_translater(MODULE_NAME)
        schemas = []
        schemas.append(cls.create_extra_data(
                name='is_vip',
                string=translater('Is VIP'),
                type_='boolean',
                kind='contract'))
        schemas.append(cls.create_extra_data(
                name='salary',
                string=translater('Annual Salary'),
                type_='numeric',
                kind='covered_element'))
        schemas.append(cls.create_extra_data(
                name='CSP',
                string=translater('CSP'),
                type_='selection',
                kind='covered_element',
                selection='\n'.join([
                                'CSP1: CSP1', 'CSP2: CSP2', 'CSP3: CSP3',
                                'CSP4: CSP4'])))
        ExtraData.create([x._save_values for x in schemas])

    @classmethod
    def create_rule(cls, **kwargs):
        RuleEngine = Pool().get('rule_engine')
        return RuleEngine(**kwargs)

    @classmethod
    def new_rule(cls, name, code, tables=None):
        Table = Pool().get('table')
        Context = Pool().get('rule_engine.context')
        if not tables:
            tables = []
        return cls.create_rule(
            name=name,
            short_name=coop_string.slugify(name),
            algorithm=code,
            parameters=[],
            context=Context(1),
            tables_used=Table.search([('code', 'in', tables)]))

    @classmethod
    def ceiling_rule_test_case(cls):
        RuleEngine = Pool().get('rule_engine')
        rules = []
        for (name, factor) in [('Plafond TA', 1), ('Plafond TB', 4),
                    ('Plafond TC', 8), ('Plafond T2', 3)]:
            rules.append(cls.new_rule(name,
                    'PMSS = table_PMSS(date_de_calcul())\n'
                    'return %s * PMSS' % factor,
                    tables=['PMSS']))
        RuleEngine.create([x._save_values for x in rules])

    @classmethod
    def create_salary_range(cls, **kwargs):
        SalaryRange = Pool().get('salary_range')
        return SalaryRange(**kwargs)

    @classmethod
    def new_salary_range(cls, code, floor_name=None, ceiling_name=None):
        Rule = Pool().get('rule_engine')
        floor = Rule.search([
                ('name', '=', floor_name)])[0].id if floor_name else None
        ceiling = Rule.search([
                ('name', '=', ceiling_name)])[0].id if ceiling_name else None
        return cls.create_salary_range(
            code=code, versions=[{'floor': floor, 'ceiling': ceiling}])

    @classmethod
    def salary_range_test_case(cls):
        SalaryRange = Pool().get('salary_range')
        result = []
        result.append(cls.new_salary_range('TA', ceiling_name='Plafond TA'))
        result.append(cls.new_salary_range('TB', floor_name='Plafond TA',
                ceiling_name='Plafond TB'))
        result.append(cls.new_salary_range('TC', floor_name='Plafond TB',
                ceiling_name='Plafond TC'))
        result.append(cls.new_salary_range('TD', floor_name='Plafond TC'))
        result.append(cls.new_salary_range('T1', ceiling_name='Plafond TA'))
        result.append(cls.new_salary_range('T2', floor_name='Plafond TA',
                ceiling_name='Plafond T2'))
        SalaryRange.create([x._save_values for x in result])

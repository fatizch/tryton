from trytond.pool import PoolMeta, Pool

MODULE_NAME = 'life_product'

__all__ = [
    'TestCaseModel',
    ]


class TestCaseModel():
    'Test Case Model'

    __metaclass__ = PoolMeta
    __name__ = 'ir.test_case'

    @classmethod
    def _get_test_case_dependencies(cls):
        result = super(TestCaseModel, cls)._get_test_case_dependencies()
        result['shared_complementary_data_test_case'] = {
            'name': 'Shared Complementary Data Test Case',
            'dependencies': set([]),
        }
        result['ceiling_rule_test_case'] = {
            'name': 'Ceiling Rule Test Case',
            'dependencies': set(['table_test_case']),
        }
        result['tranche_test_case'] = {
            'name': 'Tranche Test Case',
            'dependencies': set(['ceiling_rule_test_case']),
        }
        return result

    @classmethod
    def get_or_create_complementary_data(cls, name, string=None, type_=None,
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
    def shared_complementary_data_test_case(cls):
        translater = cls.get_translater(MODULE_NAME)
        schemas = []
        schemas.append(cls.get_or_create_complementary_data('is_vip',
                translater('Is VIP'), 'boolean', 'contract'))
        schemas.append(cls.get_or_create_complementary_data('salary',
                translater('Annual Salary'), 'numeric', 'sub_elem'))
        schemas.append(cls.get_or_create_complementary_data('CSP',
                translater('CSP'), 'selection', 'sub_elem', '\n'.join([
                                'CSP1: CSP1', 'CSP2: CSP2', 'CSP3: CSP3',
                                'CSP4: CSP4'])))
        return schemas

    @classmethod
    def create_rule(cls, name, code, tables=None):
        RuleEngine = Pool().get('rule_engine')
        RuleParameter = Pool().get('rule_engine.parameter')
        Table = Pool().get('table.table_def')
        Context = Pool().get('rule_engine.context')
        existing = RuleEngine.search([('name', '=', name)])
        if existing:
            return existing[0]
        if not tables:
            tables = []
        rule = RuleEngine()
        rule.name = name
        rule.code = code
        rule.rule_parameters = []
        rule.context = Context(1)
        for elem in tables:
            param = RuleParameter()
            param.kind = 'table'
            param.code = elem
            param.the_table = Table.search([('code', '=', elem)])[0]
            param.name = param.the_table.name
            rule.rule_parameters.append(param)
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
    def create_tranche(cls, code, floor_name=None, ceiling_name=None):
        Tranche = Pool().get('salary_range')
        TrancheVersion = Pool().get('salary_range.version')
        Rule = Pool().get('rule_engine')
        tranche = Tranche()
        tranche.code = code
        version = TrancheVersion()
        if floor_name:
            version.floor = Rule.search([('name', '=', floor_name)])[0]
        if ceiling_name:
            version.floor = Rule.search([('name', '=', ceiling_name)])[0]
        tranche.versions = [version]
        return tranche

    @classmethod
    def tranche_test_case(cls):
        result = []
        result.append(cls.create_tranche('TA', ceiling_name='Plafond TA'))
        result.append(cls.create_tranche('TB', floor_name='Plafond TA',
                ceiling_name='Plafond TB'))
        result.append(cls.create_tranche('TC', floor_name='Plafond TB',
                ceiling_name='Plafond TC'))
        result.append(cls.create_tranche('TD', floor_name='Plafond TC'))
        result.append(cls.create_tranche('T1', ceiling_name='Plafond TA'))
        result.append(cls.create_tranche('T2', floor_name='Plafond TA',
                ceiling_name='Plafond T2'))
        return result

from trytond.pool import PoolMeta, Pool


MODULE_NAME = 'offered_insurance'

__metaclass__ = PoolMeta
__all__ = [
    'TestCaseModel',
    ]


class TestCaseModel:
    __name__ = 'ir.test_case'

    @classmethod
    def _get_test_case_dependencies(cls):
        result = super(TestCaseModel, cls)._get_test_case_dependencies()
        result['contact_mechanism_test_case']['dependencies'].add(
            'insurer_test_case')
        result['insurer_test_case'] = {
            'name': 'Insurer Test Case',
            'dependencies': set(['configure_accounting_test_case']),
            }
        result['extra_premium_kind_test_case'] = {
            'name': 'Extra Premium Kind Test Case',
            'dependencies': set(),
            }
        return result

    @classmethod
    def insurer_test_case(cls):
        Insurer = Pool().get('insurer')
        cls.load_resources(MODULE_NAME)
        insurer_file = cls.read_data_file('insurer', MODULE_NAME, ';')
        insurers = []
        for insurer_data in insurer_file:
            insurer_party = cls.create_company(insurer_data[1],
                insurer_data[0])
            insurer_party.insurer_role = [Insurer()]
            insurers.append(insurer_party)
        return insurers

    @classmethod
    def create_extra_premium_kind(cls, code, name):
        ExtraPremiumKind = Pool().get('extra_premium.kind')
        new_extra = ExtraPremiumKind()
        new_extra.code = code
        new_extra.name = name
        return new_extra

    @classmethod
    def extra_premium_kind_test_case(cls):
        translater = cls.get_translater(MODULE_NAME)
        extra_kinds = []
        for code, name in [
                ('medical_risk', 'Medical Risk'),
                ('professional_risk', 'Professional Risk'),
                ('sport_risk', 'Sport Risk')]:
            extra_kinds.append(cls.create_extra_premium_kind(
                    translater(code), translater(name)))
        return extra_kinds

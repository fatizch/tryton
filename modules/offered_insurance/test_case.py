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

from trytond.pool import PoolMeta, Pool


MODULE_NAME = 'insurance_product'

__all__ = [
    'TestCaseModel',
    ]


class TestCaseModel():
    'Test Case Model'

    __metaclass__ = PoolMeta
    __name__ = 'coop_utils.test_case_model'

    @classmethod
    def _get_test_case_dependencies(cls):
        result = super(TestCaseModel, cls)._get_test_case_dependencies()
        result['contact_mechanism_test_case']['dependencies'].add(
            'insurer_test_case')
        result['insurer_test_case'] = {
            'name': 'Insurer Test Case',
            'dependencies': set([]),
        }
        return result

    @classmethod
    def insurer_test_case(cls):
        Insurer = Pool().get('party.insurer')
        cls.load_resources(MODULE_NAME)
        insurer_file = cls.read_data_file('insurer', MODULE_NAME, ';')
        insurers = []
        for insurer_data in insurer_file:
            insurer_party = cls.create_company(insurer_data[1],
                insurer_data[0])
            insurer_party.insurer_role = [Insurer()]
            insurers.append(insurer_party)
        return insurers

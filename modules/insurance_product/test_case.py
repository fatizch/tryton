from trytond.pool import PoolMeta, Pool

from trytond.modules.coop_utils import set_test_case

MODULE_NAME = 'insurance_product'

__all__ = [
    'TestCaseModel',
    ]


class TestCaseModel():
    'Test Case Model'

    __metaclass__ = PoolMeta
    __name__ = 'coop_utils.test_case_model'

    @classmethod
    def __setup__(cls):
        super(TestCaseModel, cls).__setup__()
        cls.contact_mechanism_test_case._dependencies.append(
            'insurer_test_case')

    @classmethod
    @set_test_case('Insurer Test Case')
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

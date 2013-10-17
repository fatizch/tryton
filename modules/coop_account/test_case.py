import datetime
from decimal import Decimal

from trytond.pool import PoolMeta, Pool

MODULE_NAME = 'coop_account'

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
        result['tax_test_case'] = {
            'name': 'Tax Test Case',
            'dependencies': set([]),
        }
        return result

    @classmethod
    def create_tax_from_line(cls, tax_data):
        TaxDesc = Pool().get('coop_account.tax_desc')
        TaxVersion = Pool().get('coop_account.tax_version')
        tax = TaxDesc()
        tax.code = tax_data[0]
        tax.name = tax_data[1]
        tax.description = tax_data[5]
        version = TaxVersion()
        version.kind = tax_data[4]
        version.value = Decimal(tax_data[3])
        version.start_date = datetime.datetime.strptime(tax_data[2],
            '%d/%m/%Y')
        tax.versions = [version]
        return tax

    @classmethod
    def tax_test_case(cls):
        cls.load_resources(MODULE_NAME)
        tax_file = cls.read_data_file('taxes', MODULE_NAME, ';')
        taxes = []
        for tax_data in tax_file:
            taxes.append(cls.create_tax_from_line(tax_data))
        return taxes

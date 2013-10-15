import datetime
from decimal import Decimal

from trytond.pool import PoolMeta, Pool
from trytond.modules.coop_utils import set_test_case

MODULE_NAME = 'coop_account'

__all__ = [
    'TestCaseModel',
    ]


class TestCaseModel():
    'Test Case Model'

    __metaclass__ = PoolMeta
    __name__ = 'coop_utils.test_case_model'

    @classmethod
    @set_test_case('Taxes Test Case')
    def tax_test_case(cls):
        TaxDesc = Pool().get('coop_account.tax_desc')
        TaxVersion = Pool().get('coop_account.tax_version')
        cls.load_resources(MODULE_NAME)
        tax_file = cls.read_data_file('taxes', MODULE_NAME, ';')
        taxes = []
        for tax_data in tax_file:
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
            taxes.append(tax)
        return taxes

import unittest
import datetime
from mock import Mock

import trytond.tests.test_tryton
from trytond.modules.cog_utils import test_framework


class ModuleTestCase(test_framework.CoopTestCase):
    'Module Test Case'

    @classmethod
    def get_module_name(cls):
        return 'premium'

    @classmethod
    def get_models(cls):
        return {
            'Product': 'offered.product',
            'PremiumDate': 'offered.product.premium_date',
            }

    def test001_premium_date_configuration(self):
        product = self.Product()
        product.premium_dates = [
            self.PremiumDate(type_='yearly_custom_date',
                custom_date=datetime.date(2010, 1, 1)),
            self.PremiumDate(type_='yearly_on_start_date'),
            ]

        contract = Mock()
        contract.start_date = datetime.date(2014, 02, 12)
        contract.end_date = datetime.date(2015, 4, 25)
        contract.options = []
        contract.extra_datas = []

        dates = product.get_dates(contract)
        dates = sorted(list(set(dates)))
        self.assertEqual(dates, [datetime.date(2014, 02, 12),
                datetime.date(2015, 01, 01), datetime.date(2015, 02, 12)])

        contract = Mock()
        contract.start_date = datetime.date(2014, 03, 01)
        contract.end_date = datetime.date(2015, 12, 31)
        contract.options = []
        contract.extra_datas = []

        dates = product.get_dates(contract)
        dates = sorted(list(set(dates)))
        self.assertEqual(dates, [datetime.date(2014, 03, 01),
                datetime.date(2015, 01, 01), datetime.date(2015, 03, 01)])

        product.premium_dates = [
            self.PremiumDate(type_='yearly_custom_date',
                custom_date=datetime.date(2014, 04, 26))]

        dates = product.get_dates(contract)
        dates = sorted(list(set(dates)))
        self.assertEqual(dates, [datetime.date(2014, 03, 01),
                datetime.date(2014, 04, 26), datetime.date(2015, 04, 26)])


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite

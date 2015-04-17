import unittest
import datetime
from mock import Mock

import trytond.tests.test_tryton
from trytond.modules.cog_utils import test_framework


class ModuleTestCase(test_framework.CoopTestCase):
    'Module Test Case'

    module = 'premium'

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
        period = Mock()
        contract.start_date = datetime.date(2014, 02, 12)
        contract.end_date = datetime.date(2015, 4, 25)
        period.start_date = datetime.date(2014, 02, 12)
        period.end_date = datetime.date(2015, 4, 25)
        contract.activation_history = [period]
        contract.options = []
        contract.extra_datas = []

        dates = product.get_dates(contract)
        dates = sorted(list(set(dates)))
        self.assertEqual(dates, [datetime.date(2014, 02, 12),
                datetime.date(2015, 01, 01), datetime.date(2015, 02, 12)])

        contract = Mock()
        period = Mock()
        contract.start_date = datetime.date(2014, 03, 01)
        contract.end_date = datetime.date(2015, 12, 31)
        period.start_date = datetime.date(2014, 03, 01)
        period.end_date = datetime.date(2015, 12, 31)
        contract.activation_history = [period]
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

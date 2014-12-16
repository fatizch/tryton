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
            'PremiumDates': 'offered.product.premium_dates',
            }

    def test001_premium_date_configuration(self):
        premium_configuration = self.PremiumDates(
            yearly_on_new_eve=True,
            yearly_on_start_date=True,
            yearly_custom_date=None)
        contract = Mock()
        contract.start_date = datetime.date(2014, 02, 12)
        contract.end_date = datetime.date(2015, 4, 25)

        dates = premium_configuration.get_dates_for_contract(contract)
        dates = sorted(list(set(dates)))
        self.assertEqual(dates, [datetime.date(2014, 02, 12),
                datetime.date(2015, 01, 01), datetime.date(2015, 02, 12)])

        contract = Mock()
        contract.start_date = datetime.date(2014, 03, 01)
        contract.end_date = datetime.date(2015, 12, 31)

        dates = premium_configuration.get_dates_for_contract(contract)
        dates = sorted(list(set(dates)))
        self.assertEqual(dates, [datetime.date(2014, 03, 01),
                datetime.date(2015, 01, 01), datetime.date(2015, 03, 01)])

        premium_configuration2 = self.PremiumDates(
            yearly_on_new_eve=False,
            yearly_on_start_date=False,
            yearly_custom_date=datetime.date(2014, 04, 26))

        dates = premium_configuration2.get_dates_for_contract(contract)
        dates = sorted(list(set(dates)))
        self.assertEqual(dates, [datetime.date(2014, 04, 26),
                datetime.date(2015, 04, 26)])


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite

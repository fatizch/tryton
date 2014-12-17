import unittest
import datetime
from mock import Mock

import trytond.tests.test_tryton
from trytond.modules.cog_utils import test_framework


class ModuleTestCase(test_framework.CoopTestCase):
    'Module Test Case'

    @classmethod
    def get_module_name(cls):
        return 'premium_life'

    @classmethod
    def get_models(cls):
        return {
            'PremiumDates': 'offered.product.premium_dates',
            }

    def test0011_premium_date_configuration(self):
        premium_configuration = self.PremiumDates(
            yearly_on_new_eve=False,
            yearly_on_start_date=False,
            yearly_custom_date=None,
            yearly_each_covered_anniversary_date=True)
        contract = Mock()
        contract.start_date = datetime.date(2014, 03, 01)
        contract.end_date = datetime.date(2016, 12, 31)

        party = Mock()
        party.birth_date = datetime.date(1976, 10, 21)
        covered_element = Mock()
        covered_element.party = party
        covered_element.is_person = True
        contract.covered_elements = []
        contract.covered_elements.append(covered_element)

        dates = premium_configuration.get_dates_for_contract(contract)
        dates = sorted(list(set(dates)))
        self.assertEqual(dates, [datetime.date(2014, 10, 21),
             datetime.date(2015, 10, 21), datetime.date(2016, 10, 21)])


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite

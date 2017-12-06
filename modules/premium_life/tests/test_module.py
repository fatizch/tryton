# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import datetime
from mock import Mock

import trytond.tests.test_tryton
from trytond.modules.coog_core import test_framework


class ModuleTestCase(test_framework.CoogTestCase):
    'Module Test Case'

    module = 'premium_life'

    @classmethod
    def get_models(cls):
        return {
            'Product': 'offered.product',
            'PremiumDate': 'offered.product.premium_date',
            }

    def test0011_premium_date_configuration(self):
        product = self.Product()
        product.premium_dates = [
            self.PremiumDate(type_='yearly_each_covered_anniversary_date'),
            ]

        contract = Mock()
        period = Mock()
        contract.start_date = datetime.date(2014, 03, 01)
        contract.initial_start_date = datetime.date(2014, 03, 01)
        contract.end_date = datetime.date(2016, 12, 31)
        period.start_date = datetime.date(2014, 03, 01)
        period.end_date = datetime.date(2016, 12, 31)
        contract.activation_history = [period]
        contract.options = []
        contract.extra_datas = []

        party = Mock()
        party.birth_date = datetime.date(1976, 10, 21)
        covered_element = Mock()
        covered_element.party = party
        covered_element.is_person = True
        covered_element.options = []
        covered_element.sub_covered_elements = []

        covered_version = Mock()
        covered_version.start = datetime.date(2014, 12, 31)
        covered_element.versions = [covered_version]

        contract.covered_elements = []
        contract.covered_elements.append(covered_element)

        dates = product.get_dates(contract)
        dates = sorted(list(set(dates)))
        self.assertEqual(dates, [datetime.date(2014, 03, 01),
                datetime.date(2014, 10, 21), datetime.date(2014, 12, 31),
                datetime.date(2015, 10, 21), datetime.date(2016, 10, 21)])


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite

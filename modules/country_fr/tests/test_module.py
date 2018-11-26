# -*- coding: utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import unittest
import trytond.tests.test_tryton

from trytond.modules.country_fr import country
from trytond.modules.coog_core import test_framework


class ModuleTestCase(test_framework.CoogTestCase):
    '''
    Test Coog module.
    '''
    module = 'country_fr'

    def test_replace_city_name(self):
        # tests zip code
        self.assertEqual(country.Zip.
            replace_city_name_with_support_for_french_sna(
                "SAINT ÉVRY-SUR-L'EAU"), 'ST EVRY SUR L EAU')

        self.assertEqual(country.Zip.
            replace_city_name_with_support_for_french_sna("SAINTE-ANNE"),
            "STE ANNE")

        # at least one space after
        self.assertEqual(country.Zip.
            replace_city_name_with_support_for_french_sna("SAINT"), "SAINT")

        self.assertEqual(country.Zip.
            replace_city_name_with_support_for_french_sna("AB SAINT CD"),
            "AB ST CD")

        self.assertEqual(country.Zip.
            replace_city_name_with_support_for_french_sna("AB SAINTE CD"),
            "AB STE CD")

        self.assertEqual(country.Zip.
            replace_city_name_with_support_for_french_sna("ABSAINTE CD"),
            "ABSAINTE CD")

        self.assertEqual(country.Zip.
            replace_city_name_with_support_for_french_sna("AB SAINTES"),
            "AB SAINTES")

        self.assertEqual(country.Zip.
            replace_city_name_with_support_for_french_sna("%ab saint cd%"),
            "AB ST CD")

        self.assertEqual(country.Zip.
            replace_city_name_with_support_for_french_sna(
                "%SAINT JUST SAINTE MARIÉ%"), "ST JUST STE MARIE")

        self.assertEqual(country.Zip.
            replace_city_name_with_support_for_french_sna(
                "%SAINT SAINT%"), "ST SAINT")


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite

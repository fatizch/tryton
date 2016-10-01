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
                u"SAINT ÉVRY-SUR-L'EAU"), u'ST EVRY SUR L EAU')

        self.assertEqual(country.Zip.
            replace_city_name_with_support_for_french_sna(u"SAINTE-ANNE"),
            u"STE ANNE")

        # at least one space after
        self.assertEqual(country.Zip.
            replace_city_name_with_support_for_french_sna(u"SAINT"), u"SAINT")

        self.assertEqual(country.Zip.
            replace_city_name_with_support_for_french_sna(u"AB SAINT CD"),
            u"AB ST CD")

        self.assertEqual(country.Zip.
            replace_city_name_with_support_for_french_sna(u"AB SAINTE CD"),
            u"AB STE CD")

        self.assertEqual(country.Zip.
            replace_city_name_with_support_for_french_sna(u"ABSAINTE CD"),
            u"ABSAINTE CD")

        self.assertEqual(country.Zip.
            replace_city_name_with_support_for_french_sna(u"AB SAINTES"),
            u"AB SAINTES")

        self.assertEqual(country.Zip.
            replace_city_name_with_support_for_french_sna(u"%ab saint cd%"),
            u"AB ST CD")

        self.assertEqual(country.Zip.
            replace_city_name_with_support_for_french_sna(
                u"%SAINT JUST SAINTE MARIÉ%"), u"ST JUST STE MARIE")

        self.assertEqual(country.Zip.
            replace_city_name_with_support_for_french_sna(
                u"%SAINT SAINT%"), u"ST SAINT")


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite

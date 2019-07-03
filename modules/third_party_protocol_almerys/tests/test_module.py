import doctest
import unittest
from lxml.builder import ElementMaker

import trytond.tests.test_tryton
from trytond.modules.coog_core import test_framework
from trytond.tests.test_tryton import doctest_teardown
from trytond.modules.third_party_protocol_almerys.batch import (
    empty_element, AlmerysElementMaker)


class ModuleTestCase(test_framework.CoogTestCase):
    'Module Test Case'

    module = 'third_party_protocol_almerys'

    def test_empty_element(self):
        E = ElementMaker()

        self.assertTrue(empty_element(None))
        self.assertTrue(empty_element(''))
        self.assertTrue(empty_element('   '))
        self.assertFalse(empty_element(' abc '))
        self.assertFalse(empty_element(0))
        self.assertFalse(empty_element(E.root()))

    def test_almerys_element_maker(self):
        E = AlmerysElementMaker()

        root = E.root(
            E.empty(),
            None,
            '')
        self.assertEqual(len(root), 1)
        self.assertEqual(root[0].tag, 'empty')


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    suite.addTests(doctest.DocFileSuite(
        'scenario_almerys_batch.rst',
        tearDown=doctest_teardown, encoding='utf8',
        optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite

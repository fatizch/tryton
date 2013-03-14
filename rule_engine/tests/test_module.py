# -*- coding: utf-8 -*-
import sys
import os
DIR = os.path.abspath(os.path.normpath(os.path.join(
    __file__, '..', '..', '..', '..', '..', 'trytond')))
if os.path.isdir(DIR):
    sys.path.insert(0, os.path.dirname(DIR))

import unittest
import trytond.tests.test_tryton

from trytond.model import ModelView
from trytond.pool import Pool
from trytond.transaction import Transaction

from trytond.modules.coop_utils import test_framework, prepare_test

MODULE_NAME = os.path.basename(
    os.path.abspath(
        os.path.join(os.path.normpath(__file__), '..', '..')))


class ModuleTestCase(test_framework.CoopTestCase):
    '''
    Test Coop module.
    '''

    @classmethod
    def get_module_name(cls):
        return MODULE_NAME

    @classmethod
    def get_models(cls):
        return {
            'TreeElement': 'rule_engine.tree_element',
            'Context': 'rule_engine.context',
            'RuleEngine': 'rule_engine',
            'TestCase': 'rule_engine.test_case',
            'TestCaseValue': 'rule_engine.test_case.value',
            'RunTests': 'rule_engine.run_tests',
        }

    @classmethod
    def depending_modules(cls):
        return ['table']

    @prepare_test('table.test0060table_2dim')
    def test0010_testTableTreeElementCreation(self):
        test_table = self.Definition.search([
            ('code', '=', 'test_code')])[0]
        table_tree = self.TreeElement.search([
            ('the_table', '=', test_table)])
        self.assertEqual(len(table_tree), 1)
        table_tree = table_tree[0]
        self.assertEqual(table_tree.fct_args, 'Value, Range')

    def test0011_testCleanValues(self):
        te = self.TreeElement()
        te.type = 'function'
        te.name = 'test_values'
        te.translated_technical_name = 'values_testé'
        te.fct_args = 'Test, Qsd'
        te.description = 'Test Values'
        te.namespace = 'rule_engine_tests'
        te.language = 1

        self.assertRaises(trytond.error.UserError, te.save)
        te.translated_technical_name = 'values_test'
        te.save()
        te.fct_args = 'Test, Qsdé'
        self.assertRaises(trytond.error.UserError, te.save)

    @prepare_test('table.test0060table_2dim')
    def test0020_testRuleEngine(self):
        class TestRuleEngine(ModelView):
            __name__ = 'rule_engine_tests'

            @classmethod
            def test_values(cls, args, alpha):
                args['messages'].append('Toto')
                args['errors'].append('Titi')
                return alpha * 2

            @classmethod
            def test_values_inexisting(cls, args):
                return 200

        Language = Pool().get('ir.lang')

        Pool().register(TestRuleEngine, type_='model', module=MODULE_NAME)
        Pool().add(TestRuleEngine)

        te = self.TreeElement()
        te.type = 'function'
        te.name = 'test_values'
        te.translated_technical_name = 'values_test'
        te.description = 'Test Values'
        te.namespace = 'rule_engine_tests'
        te.language, = Language.search([('code', '=', 'en_US')])

        te.save()

        te1 = self.TreeElement()
        te1.type = 'function'
        te1.name = 'test_values_inexisting'
        te1.translated_technical_name = 'inexisting_test_values'
        te1.description = 'Test Values'
        te1.namespace = 'rule_engine_tests'
        te1.language, = Language.search([('code', '=', 'en_US')])

        te1.save()

        te2 = self.TreeElement()
        te2.type = 'table'
        te2.translated_technical_name = 'table_test_code'
        te2.description = 'Table Test'
        te2.the_table = self.Definition.search([('code', '=', 'test_code')])[0]
        te2.language, = Language.search([('code', '=', 'en_US')])

        te2.save()

        ct = self.Context()
        ct.name = 'test_context'
        ct.allowed_elements = []
        ct.allowed_elements.append(te)
        ct.allowed_elements.append(te1)
        ct.allowed_elements.append(te2)

        ct.save()

        rule = self.RuleEngine()
        rule.name = 'test_rule'
        rule.context = ct
        rule.code = '''
if table_test_code('bar', 5) != 'spam':
    return 0

return values_test(inexisting_test_values()) * 1.0
'''

        tcv = self.TestCaseValue()
        tcv.name = 'inexisting_test_values'
        tcv.value = '4'

        tc = self.TestCase()
        tc.description = 'Test'
        tc.values = [tcv]
        tc.expected_result = "(8, ['Toto'], ['Titi'])"

        rule.test_cases = [tc]

        rule.save()

        with Transaction().set_context({'active_id': rule.id}):
            wizard_id, _, _ = self.RunTests.create()
            wizard = self.RunTests(wizard_id)
            wizard._execute('report')
            res = wizard.default_report(None)
            self.assertEqual(res, {'report': 'Test ... SUCCESS'})


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())

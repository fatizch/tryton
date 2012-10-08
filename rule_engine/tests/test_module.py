import sys
import os
DIR = os.path.abspath(os.path.normpath(os.path.join(__file__,
    '..', '..', '..', '..', '..', 'trytond')))
if os.path.isdir(DIR):
    sys.path.insert(0, os.path.dirname(DIR))

import unittest
import trytond.tests.test_tryton
from trytond.model import ModelView
from trytond.tests.test_tryton import test_view, test_depends
from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT
from trytond.transaction import Transaction


MODULE_NAME = os.path.basename(
                  os.path.abspath(
                      os.path.join(os.path.normpath(__file__), '..', '..')))


class ModuleTestCase(unittest.TestCase):
    '''
    Test Coop module.
    '''

    def setUp(self):
        trytond.tests.test_tryton.install_module(MODULE_NAME)
        self.TreeElement = POOL.get('rule_engine.tree_element')
        self.Context = POOL.get('rule_engine.context')
        self.RuleEngine = POOL.get('rule_engine')
        self.TestCase = POOL.get('rule_engine.test_case')
        self.TestCaseValue = POOL.get('rule_engine.test_case.value')
        self.RunTests = POOL.get('rule_engine.run_tests', type='wizard')

    def test0005views(self):
        '''
        Test views.
        '''
        test_view(MODULE_NAME)

    def test0006depends(self):
        '''
        Test depends.
        '''
        test_depends()

    def test0010_testRuleEngine(self):
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

        Language = POOL.get('ir.lang')

        with Transaction().start(DB_NAME,
                                 USER,
                                 context=CONTEXT) as transaction:
            POOL.register(TestRuleEngine, type_='model', module=MODULE_NAME)
            POOL.add(TestRuleEngine)

            te = self.TreeElement()
            te.type = 'function'
            te.name = te.translated_technical_name = 'test_values'
            te.description = 'Test Values'
            te.namespace = 'rule_engine_tests'
            te.language, = Language.search([('code', '=', 'en_US')])

            te.save()

            te1 = self.TreeElement()
            te1.type = 'function'
            te1.name = te1.translated_technical_name = 'test_values_inexisting'
            te1.description = 'Test Values'
            te1.namespace = 'rule_engine_tests'
            te1.language, = Language.search([('code', '=', 'en_US')])

            te1.save()

            ct = self.Context()
            ct.name = 'test_context'
            ct.allowed_elements = []
            ct.allowed_elements.append(te)
            ct.allowed_elements.append(te1)

            ct.save()

            rule = self.RuleEngine()
            rule.name = 'test_rule'
            rule.context = ct
            rule.code = 'return test_values(test_values_inexisting())'

            tcv = self.TestCaseValue()
            tcv.name = 'test_values_inexisting'
            tcv.value = '4'

            tc = self.TestCase()
            tc.description = 'Test'
            tc.values = [tcv]
            tc.expected_result = '(8, ["Toto"], ["Titi"])'

            rule.test_cases = [tc]

            rule.save()

            with transaction.set_context({'active_id': rule.id}):
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

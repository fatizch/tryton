import sys
import os
DIR = os.path.abspath(os.path.normpath(os.path.join(__file__,
    '..', '..', '..', '..', '..', 'trytond')))
if os.path.isdir(DIR):
    sys.path.insert(0, os.path.dirname(DIR))

import unittest
import trytond.tests.test_tryton
from trytond.tests.test_tryton import test_view, test_depends
from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT
from trytond.transaction import Transaction


class RuleEngineTestCase(unittest.TestCase):
    '''
    Test Rule Engine module.
    '''

    def setUp(self):
        trytond.tests.test_tryton.install_module('rule_engine')
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
        test_view('rule_engine')

    def test0006depends(self):
        '''
        Test depends.
        '''
        test_depends()

    def test0010_testRuleEngine(self):
        with Transaction().start(DB_NAME,
                                 USER,
                                 context=CONTEXT) as transaction:
            te = self.TreeElement()
            te.type = 'function'
            te.name = 'test_values'
            te.description = 'Test Values'
            te.namespace = te.__name__

            te.save()

            te1 = self.TreeElement()
            te1.type = 'function'
            te1.name = 'test_values_inexisting'
            te1.description = 'Test Values'
            te1.namespace = te1.__name__

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
        RuleEngineTestCase))
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())

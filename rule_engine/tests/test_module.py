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
        self.definition = POOL.get('table.table_def')
        self.dimension = POOL.get('table.table_dimension')
        self.cell = POOL.get('table.table_cell')

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

    def create_test_table(self):
        definition = self.definition.create({
                'name': 'Test',
                'code': 'test_table_awesome',
                'dimension_kind1': 'value',
                'dimension_kind2': 'range',
                })
        dim1_foo = self.dimension.create({
                'definition': definition.id,
                'type': 'dimension1',
                'value': 'foo',
                })
        dim1_bar = self.dimension.create({
                'definition': definition.id,
                'type': 'dimension1',
                'value': 'bar',
                })
        dim2_foo = self.dimension.create({
                'definition': definition.id,
                'type': 'dimension2',
                'start': 1,
                'end': 10,
                })
        dim2_bar = self.dimension.create({
                'definition': definition.id,
                'type': 'dimension2',
                'start': 20,
                'end': 42,
                })
        for values in (
                {'dimension1': dim1_foo.id, 'dimension2': dim2_foo.id,
                    'value': 'ham'},
                {'dimension1': dim1_bar.id, 'dimension2': dim2_foo.id,
                    'value': 'spam'},
                {'dimension1': dim1_foo.id, 'dimension2': dim2_bar.id,
                    'value': 'egg'},
                {'dimension1': dim1_bar.id, 'dimension2': dim2_bar.id,
                    'value': 'chicken'}):
            values.update({
                    'definition': definition.id,
                    })
            self.cell.create(values)

        return definition

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
            te2.translated_technical_name = 'table_test_table_awesome'
            te2.description = 'Table Test'
            te2.the_table = self.create_test_table()
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
if table_test_table_awesome('bar', 5) != 'spam':
    return 0

return values_test(inexisting_test_values())
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

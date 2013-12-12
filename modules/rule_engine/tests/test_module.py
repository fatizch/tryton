# -*- coding: utf-8 -*-
import unittest
import trytond.tests.test_tryton

from trytond.transaction import Transaction
from trytond.error import UserError

from trytond.modules.coop_utils import test_framework


class ModuleTestCase(test_framework.CoopTestCase):
    '''
    Test Coop module.
    '''

    @classmethod
    def get_module_name(cls):
        return 'rule_engine'

    @classmethod
    def get_models(cls):
        return {
            'TreeElement': 'rule_engine.tree_element',
            'Context': 'rule_engine.context',
            'RuleEngine': 'rule_engine',
            'TestCase': 'rule_engine.test_case',
            'TestCaseValue': 'rule_engine.test_case.value',
            'RunTests': 'rule_engine.run_tests',
            'Language': 'ir.lang',
            'RuleParameter': 'rule_engine.parameter',
            'Table': 'table.table_def',
        }

    @classmethod
    def depending_modules(cls):
        return ['table']

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

    def test0012_createRuleToolsTreeElements(self):
        english = self.Language.search([('code', '=', 'en_US')])

        def create_tree_elem(the_type, name, translated_name, namespace,
                description):
            te = self.TreeElement()
            te.type = the_type
            te.name = name
            te.translated_technical_name = translated_name
            te.description = description
            te.namespace = namespace
            te.language = english[0]
            te.save()
            return te

        create_tree_elem('function', '_re_today', 'today',
            'rule_engine.runtime', 'Today')
        create_tree_elem('function', '_re_add_error', 'add_error',
            'rule_engine.runtime', 'Add Error')
        create_tree_elem('function', '_re_add_warning', 'add_warning',
            'rule_engine.runtime', 'Add Warning')
        create_tree_elem('function', '_re_add_info', 'add_info',
            'rule_engine.runtime', 'Add Info')
        create_tree_elem('function', '_re_add_error_code',
            'add_error_code', 'rule_engine.runtime', 'Add Error Code')
        create_tree_elem('function', '_re_debug', 'add_debug',
            'rule_engine.runtime', 'Add Debug')
        create_tree_elem('function', '_re_calculation_date',
            'calculation_date', 'rule_engine.runtime',
            'Calculation Date')

    @test_framework.prepare_test(
        'rule_engine.test0012_createRuleToolsTreeElements')
    def test0013_createTestContext(self):
        ct = self.Context()
        ct.name = 'test_context'
        ct.allowed_elements = []
        for elem in self.TreeElement.search([('language.code', '=', 'en_US')]):
            ct.allowed_elements.append(elem)
        self.assertEqual(len(ct.allowed_elements), 7)
        ct.save()
        return ct

    @test_framework.prepare_test('rule_engine.test0013_createTestContext')
    def test0014_testRuleEngineCreation(self):
        ct = self.Context.search([('name', '=', 'test_context')])[0]
        rule = self.RuleEngine()
        rule.code = rule.default_code()
        self.assertEqual(rule.code, 'return')
        rule.name = 'Test Rule'
        rule.rule_parameters = []
        rule.context = ct
        tree_structure = rule.data_tree_structure()
        target_tree_structure = [
            {
                'description': "Add Debug",
                'fct_args': "",
                'long_description': "",
                'translated': "add_debug",
                'type': "function",
                'children': [],
                'name': "_re_debug",
                },
            {
                'description': "Add Error",
                'fct_args': "",
                'long_description': "",
                'translated': "add_error",
                'type': "function",
                'children': [],
                'name': "_re_add_error",
                },
            {
                'description': "Add Error Code",
                'fct_args': "",
                'long_description': "",
                'translated': "add_error_code",
                'type': "function",
                'children': [],
                'name': "_re_add_error_code",
                },
            {
                'description': "Add Info",
                'fct_args': "",
                'long_description': "",
                'translated': "add_info",
                'type': "function",
                'children': [],
                'name': "_re_add_info",
                },
            {
                'description': "Add Warning",
                'fct_args': "",
                'long_description': "",
                'translated': "add_warning",
                'type': "function",
                'children': [],
                'name': "_re_add_warning",
                },
            {
                'description': "Calculation Date",
                'fct_args': "",
                'long_description': "",
                'translated': "calculation_date",
                'type': "function",
                'children': [],
                'name': "_re_calculation_date",
                },
            {
                'description': "Today",
                'fct_args': "",
                'long_description': "",
                'translated': "today",
                'type': "function",
                'children': [],
                'name': "_re_today",
                },
            ]
        self.assertEqual(tree_structure, target_tree_structure)

        # Check default code validates
        self.assertEqual(rule.validate([rule]), True)
        # Check context elem code validates
        rule.code = 'return today()'
        self.assertEqual(rule.validate([rule]), True)
        # Check warnings validates
        rule.code = 'toto = 10\n'
        rule.code += 'return today()'
        self.assertEqual(rule.validate([rule]), True)
        # Check unknown symbols fail
        rule.code = 'return some_unknown_symbol'
        self.assertRaises(UserError, rule.validate, [rule])
        # Check syntax errors fail
        rule.code = 'if 10'
        rule.code += ' return'
        self.assertRaises(UserError, rule.validate, [rule])

        rule.code = 'return 10.0'
        rule.save()

        self.assertEqual(rule.allowed_functions, [
                'add_debug', 'add_error', 'add_error_code', 'add_info',
                'add_warning', 'calculation_date', 'today'])
        # Check as_function, code template and decistmt behaviour
        func_code = rule.as_function.split('\n')
        func_id = ('%s' % hash(rule.name)).replace('-', '_')
        self.assertEqual(func_code, [
                u'',
                u'def fct_%s ():' % func_id,
                u' from decimal import Decimal ',
                u' return Decimal (u\'10.0\')',
                u'',
                u'result_%s =fct_%s ()' % (func_id, func_id),
                u''])

    @test_framework.prepare_test('table.test0060table_2dim',
        'rule_engine.test0014_testRuleEngineCreation')
    def test0015_testExternalParameterTable(self):
        rule = self.RuleEngine.search([('name', '=', 'Test Rule')])[0]
        rule.code = 'return table_test_code(\'bar\', 5)'
        self.assertRaises(UserError, rule.validate, [rule])

        table = self.Table.search([('code', '=', 'test_code')])[0]
        table_parameter = self.RuleParameter()
        table_parameter.kind = 'table'
        table_parameter.the_table = table
        self.assertEqual(table_parameter.on_change_the_table(), {
                'code': table.code, 'name': table.name})
        table_parameter.code = table.code
        table_parameter.name = table.name
        table_parameter.parent_rule = rule
        table_parameter.save()

        tree_structure = rule.data_tree_structure()[-1]
        self.assertEqual(tree_structure, {
                'description': 'Extra Args',
                'fct_args': '',
                'long_description': '',
                'name': 'extra args',
                'translated': 'extra args',
                'type': 'folder',
                'children': [{
                        'description': 'Tables',
                        'fct_args': '',
                        'long_description': '',
                        'name': 'tables',
                        'translated': 'tables',
                        'type': 'folder',
                        'children': [
                            {
                                'description': u'Test',
                                'fct_args': u'Value, Range',
                                'long_description': u'Test (table)',
                                'name': u'Test',
                                'translated': u'table_test_code',
                                'type': 'function',
                                'children': [],
                                }]}]})

        self.assertEqual(rule.validate([rule]), True)

    @test_framework.prepare_test('rule_engine.test0014_testRuleEngineCreation')
    def test0016_testExternalParameterKwarg(self):
        rule = self.RuleEngine.search([('name', '=', 'Test Rule')])[0]
        rule.code = 'return kwarg_test_parameter()'
        self.assertRaises(UserError, rule.validate, [rule])

        kwarg_parameter = self.RuleParameter()
        kwarg_parameter.kind = 'kwarg'
        kwarg_parameter.code = 'test_parameter'
        kwarg_parameter.name = 'Test Parameter'
        kwarg_parameter.parent_rule = rule
        kwarg_parameter.save()

        tree_structure = rule.data_tree_structure()[-1]
        self.assertEqual(tree_structure, {
                'description': 'Extra Args',
                'fct_args': '',
                'long_description': '',
                'name': 'extra args',
                'translated': 'extra args',
                'type': 'folder',
                'children': [{
                        'description': 'X-Y-Z',
                        'fct_args': '',
                        'long_description': '',
                        'name': 'x-y-z',
                        'translated': 'x-y-z',
                        'type': 'folder',
                        'children': [
                            {
                                'description': u'Test Parameter',
                                'fct_args': '',
                                'long_description': u'Test Parameter (kwarg)',
                                'name': u'Test Parameter',
                                'translated': u'kwarg_test_parameter',
                                'type': 'function',
                                'children': [],
                                }]}]})

        self.assertEqual(rule.validate([rule]), True)

    @test_framework.prepare_test(
        'rule_engine.test0016_testExternalParameterKwarg')
    def test0017_testExternalParameterRule(self):
        rule = self.RuleEngine.search([('name', '=', 'Test Rule')])[0]
        rule.code = 'return rule_test_rule(test_parameter=True)'
        self.assertRaises(UserError, rule.validate, [rule])

        rule_parameter = self.RuleParameter()
        rule_parameter.kind = 'rule'
        rule_parameter.the_rule = rule
        self.assertEqual(rule_parameter.on_change_the_rule(), {
                'code': 'test_rule', 'name': rule.name})
        rule_parameter.name = 'Test Rule'
        rule_parameter.code = 'test_rule'
        rule_parameter.parent_rule = rule
        rule_parameter.save()

        tree_structure = rule.data_tree_structure()[-1]
        self.assertEqual(tree_structure, {
                'description': 'Extra Args',
                'fct_args': '',
                'long_description': '',
                'name': 'extra args',
                'translated': 'extra args',
                'type': 'folder',
                'children': [{
                        'description': 'X-Y-Z',
                        'fct_args': '',
                        'long_description': '',
                        'name': 'x-y-z',
                        'translated': 'x-y-z',
                        'type': 'folder',
                        'children': [
                            {
                                'description': u'Test Parameter',
                                'fct_args': '',
                                'long_description': u'Test Parameter (kwarg)',
                                'name': u'Test Parameter',
                                'translated': u'kwarg_test_parameter',
                                'type': 'function',
                                'children': [],
                                }]},
                    {
                        'description': 'Rules',
                        'fct_args': '',
                        'long_description': '',
                        'name': 'rule',
                        'translated': 'rule',
                        'type': 'folder',
                        'children': [
                            {
                                'description': u'Test Rule',
                                'fct_args': 'test_parameter=',
                                'long_description': u'Test Rule (rule)',
                                'name': u'Test Rule',
                                'translated': u'rule_test_rule',
                                'type': 'function',
                                'children': [],
                                }]}]})

        self.assertEqual(rule.validate([rule]), True)

    @test_framework.prepare_test('table.test0060table_2dim',
        'rule_engine.test0014_testRuleEngineCreation')
    def test0020_testAdvancedRule(self):
        rule1 = self.RuleEngine.search([('name', '=', 'Test Rule')])[0]
        table = self.Table.search([('code', '=', 'test_code')])[0]
        kwarg_parameter = self.RuleParameter()
        kwarg_parameter.kind = 'kwarg'
        kwarg_parameter.code = 'test_parameter'
        kwarg_parameter.name = 'Test Parameter'
        kwarg_parameter.parent_rule = rule1
        kwarg_parameter.save()
        rule1.code = 'return kwarg_test_parameter()'
        rule1.save()

        rule = self.RuleEngine()
        rule.name = 'Test Rule Advanced'
        rule.context = rule1.context
        rule_parameter = self.RuleParameter()
        rule_parameter.kind = 'rule'
        rule_parameter.the_rule = rule1
        rule_parameter.name = 'Test Rule'
        rule_parameter.code = 'test_rule'
        rule_parameter.parent_rule = rule
        rule_parameter.save()
        table_parameter = self.RuleParameter()
        table_parameter.kind = 'table'
        table_parameter.the_table = table
        table_parameter.code = table.code
        table_parameter.name = table.name
        table_parameter.parent_rule = rule
        table_parameter.save()

        rule.code = '\n'.join([
                'if table_test_code(\'test\', 30):',
                '    return 10',
                'add_error(\'test error\')',
                'add_warning(\'test warning\')',
                'add_info(\'test info\')',
                'if table_test_code(\'foo\', 1) == \'ham\':',
                '    return rule_test_rule(test_parameter=20)'])
        rule.save()

    @test_framework.prepare_test('rule_engine.test0020_testAdvancedRule')
    def test0021_testRuleEngineExecution(self):
        rule, = self.RuleEngine.search([('name', '=', 'Test Rule Advanced')])
        result = rule.execute({})
        self.assertEqual(result.result, 20)
        self.assertEqual(result.errors, ['test error'])
        self.assertEqual(result.warnings, ['test warning'])
        self.assertEqual(result.info, ['test info'])
        self.assertEqual(result.low_level_debug, [u'Entering table_test_code',
                "\targs : ('test', 30)",
                '\tresult = None',
                u'Entering add_error',
                "\targs : ('test error',)",
                '\tresult = None',
                u'Entering add_warning',
                "\targs : ('test warning',)",
                '\tresult = None',
                u'Entering add_info',
                "\targs : ('test info',)",
                '\tresult = None',
                u'Entering table_test_code',
                "\targs : ('foo', 1)",
                '\tresult = ham',
                u'Entering rule_test_rule',
                "\tkwargs : {'test_parameter': 20}",
                '\tresult = 20'])
        self.assertEqual(rule.exec_logs, ())

    @test_framework.prepare_test('rule_engine.test0020_testAdvancedRule')
    def test0030_TestCaseCreation(self):
        rule, = self.RuleEngine.search([('name', '=', 'Test Rule Advanced')])
        with Transaction().set_context(rule_id=rule.id):
            tc = self.TestCase()
            self.assertEqual(tc.default_test_values(), [
                    {'override_value': False, 'name': 'table_test_code',
                        'value': ''},
                    {'override_value': True, 'name': 'add_error', 'value': ''},
                    {'override_value': True, 'name': 'add_warning',
                        'value': ''},
                    {'override_value': True, 'name': 'add_info',
                        'value': ''},
                    {'override_value': False, 'name':
                        'table_test_code', 'value': ''},
                    {'override_value': True, 'name': 'rule_test_rule',
                        'value': ''}])

            def create_test_case_value(name, value, override=True):
                tcv = self.TestCaseValue()
                tcv.name = name
                tcv.value = value
                tcv.override_value = override
                tcv.save()
                return tcv

            # Check override of table elements
            tcv1 = create_test_case_value('table_test_code', "'something'")
            tc = self.TestCase()
            tc.description = 'Fail Value'
            tc.rule = rule
            tc.test_values = []
            self.maxDiff = None
            self.assertEqual(tc.on_change_test_values(), {
                    'low_debug': "Entering table_test_code\n"
                    "\targs : ('test', 30)\n"
                    "\tresult = None\n"
                    "Entering add_error\n"
                    "\targs : ('test error',)\n"
                    "\tresult = None\n"
                    "Entering add_warning\n"
                    "\targs : ('test warning',)\n"
                    "\tresult = None\n"
                    "Entering add_info\n"
                    "\targs : ('test info',)\n"
                    "\tresult = None\n"
                    "Entering table_test_code\n"
                    "\targs : ('foo', 1)\n"
                    "\tresult = ham\n"
                    "Entering rule_test_rule\n"
                    "\tkwargs : {'test_parameter': 20}\n"
                    "\tresult = 20",
                    'result_warning': u'test warning',
                    'result_value': u'20',
                    'debug': '',
                    'result_errors': u'test error',
                    'expected_result': '[20, [test error], [test warning],'
                    ' [test info]]',
                    'result_info': u'test info'})
            tc.test_values = [tcv1]
            self.assertEqual(tc.on_change_test_values(), {
                    'low_debug': '',
                    'result_warning': '',
                    'result_value': '10',
                    'debug': '',
                    'result_errors': '',
                    'expected_result': '[10, [], [], []]',
                    'result_info': ''})
            tc.expected_result = "[10, [], [], []]"
            tc.save()

            # Check override of function elements
            tcv1 = create_test_case_value('add_error', "'nothing'")
            tc = self.TestCase()
            tc.description = 'Remove Errors'
            tc.test_values = [tcv1]
            tc.expected_result = '[20, [], [test warning], [test info]]'
            tc.rule = rule
            tc.save()

            # Check override of rule elements
            tcv1 = create_test_case_value('rule_test_rule', '50')
            tc = self.TestCase()
            tc.description = 'Override rule'
            tc.test_values = [tcv1]
            tc.expected_result = \
                '[50, [test error], [test warning], [test info]]'
            tc.rule = rule
            tc.save()

        with Transaction().set_context({'active_id': rule.id}):
            wizard_id, _, _ = self.RunTests.create()
            wizard = self.RunTests(wizard_id)
            wizard._execute('report')
            res = wizard.default_report(None)
            self.assertEqual(res, {'report':
                    'Fail Value ... SUCCESS\n\n'
                    'Remove Errors ... SUCCESS\n'
                    '\nOverride rule ... SUCCESS'})

    @test_framework.prepare_test('rule_engine.test0020_testAdvancedRule')
    def test0060_testRuleEngineDebugging(self):
        # This test must be run later as execute rule force a commit
        rule, = self.RuleEngine.search([('name', '=', 'Test Rule Advanced')])

        # Check Debug mode
        rule.debug_mode = True
        rule.save()
        rule.execute({})
        self.assertEqual(len(rule.exec_logs), 1)

        # Check execution errors raise UserErrors
        rule.debug_mode = False
        rule.code = 'return rule_test_rule()'
        rule.save()
        self.assertRaises(UserError, rule.execute, {})
        rule.code = 'return 1 / 0'
        rule.save()
        self.assertRaises(UserError, rule.execute, {})

        # Test that disabling debug_mode effectively delete existing logs
        rule.debug_mode = False
        rule.save()
        self.assertEqual(rule.exec_logs, ())


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())

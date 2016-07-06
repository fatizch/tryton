# -*- coding: utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import trytond.tests.test_tryton

from trytond.transaction import Transaction
from trytond.error import UserError

from trytond.modules.cog_utils import test_framework


class ModuleTestCase(test_framework.CoopTestCase):
    '''
    Test Coop module.
    '''

    module = 'rule_engine'

    @classmethod
    def get_models(cls):
        return {
            'RuleFunction': 'rule_engine.function',
            'Context': 'rule_engine.context',
            'RuleEngine': 'rule_engine',
            'TestCase': 'rule_engine.test_case',
            'TestCaseValue': 'rule_engine.test_case.value',
            'RunTests': 'rule_engine.run_tests',
            'Language': 'ir.lang',
            'RuleParameter': 'rule_engine.rule_parameter',
            'RuleEngineRuleEngine': 'rule_engine-rule_engine',
            'RuleEngineTable': 'rule_engine-table',
            'Table': 'table',
            'Log': 'rule_engine.log',
            'InitTestCaseFromExecutionLog': 'rule_engine.test_case.init',
        }

    @classmethod
    def depending_modules(cls):
        return ['table']

    def test0011_testCleanValues(self):
        te = self.RuleFunction()
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

    def test0012_createRuleToolsRuleFunction(self):
        english = self.Language.search([('code', '=', 'en_US')])

        def create_tree_elem(the_type, name, translated_name, namespace,
                description):
            te = self.RuleFunction()
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
        'rule_engine.test0012_createRuleToolsRuleFunction')
    def test0013_createTestContext(self):
        ct = self.Context()
        ct.name = 'test_context'
        allowed_elements = []
        for elem in self.RuleFunction.search([
                    ('language.code', '=', 'en_US')]):
            allowed_elements.append(elem)
        ct.allowed_elements = allowed_elements
        self.assertEqual(len(ct.allowed_elements), 7)
        ct.save()
        return ct

    @test_framework.prepare_test('rule_engine.test0013_createTestContext')
    def test0014_testRuleEngineCreation(self):
        ct = self.Context.search([('name', '=', 'test_context')])[0]
        rule = self.RuleEngine()
        rule.algorithm = rule.default_algorithm()
        self.assertEqual(rule.algorithm, 'return')
        rule.name = 'Test Rule'
        rule.short_name = 'test_rule'
        rule.context = ct
        rule.parameters = []
        rule.rules_used = []
        rule.tables_used = []
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
            {
                'children': [],
                'description': 'Parameters',
                'fct_args': '',
                'long_description': '',
                'name': '',
                'translated': '',
                'type': 'folder'
                },
            {
                'children': [],
                'description': 'Rules',
                'fct_args': '',
                'long_description': '',
                'name': '',
                'translated': '',
                'type': 'folder'
                },
            {
                'children': [],
                'description': 'Tables',
                'fct_args': '',
                'long_description': '',
                'name': '',
                'translated': '',
                'type': 'folder'
                }
            ]

        self.assertEqual(tree_structure, target_tree_structure)

        # Check default code validates
        with Transaction().set_user(1):
            rule.save()
            self.assertEqual(rule.check_code(), True)
            # Check context elem code validates
            rule.algorithm = 'return today()'
            rule.save()
            self.assertEqual(rule.check_code(), True)
            # Check warnings validates
            rule.algorithm = 'toto = 10\n'
            rule.algorithm += 'return today()'
            rule.save()
            self.assertEqual(rule.check_code(), True)
            # Check unknown symbols fail
            rule.algorithm = 'return some_unknown_symbol'
            rule.save()
            self.assertRaises(UserError, rule.check_code)
            # Check syntax errors fail
            rule.algorithm = 'if 10'
            rule.algorithm += ' return'
            self.assertRaises(UserError, rule.check_code)

            rule.algorithm = 'return 10.0'
            rule.save()

        self.assertEqual(set(rule.allowed_functions()), {
                'add_debug', 'add_error', 'add_error_code', 'add_info',
                'add_warning', 'calculation_date', 'today',
                'datetime', 'Decimal', 'relativedelta'})
        # Check execution_code, code template and decistmt behaviour
        func_code = rule.execution_code.split('\n')
        func_id = ('%s' % hash(rule.name)).replace('-', '_')
        self.assertEqual(func_code, [
                u'',
                u'def fct_%s ():' % func_id,
                u' return Decimal (u\'10.0\')',
                u'',
                u'result_%s =fct_%s ()' % (func_id, func_id),
                u''])

    @test_framework.prepare_test('table.test0060table_2dim',
        'rule_engine.test0014_testRuleEngineCreation')
    def test0015_testExternalParameterTable(self):
        rule = self.RuleEngine.search([('name', '=', 'Test Rule')])[0]
        rule.algorithm = 'return table_test_code(\'bar\', 5)'
        rule.save()
        with Transaction().set_user(1):
            self.assertRaises(UserError, rule.check_code)

        table = self.Table.search([('code', '=', 'test_code')])[0]
        table_parameter = self.RuleEngineTable()
        table_parameter.table = table
        table_parameter.parent_rule = rule
        table_parameter.save()

        tree_structure = rule.data_tree_structure()[-1]
        self.assertEqual(tree_structure, {
            'description': 'Tables',
            'fct_args': '',
            'long_description': '',
            'name': '',
            'translated': '',
            'type': 'folder',
            'children': [{'children': [],
                          'description': u'Test',
                          'fct_args': u'Value, Range',
                          'long_description': u'Test (table)',
                          'name': 'UnusedVariable',
                          'translated': u'table_test_code',
                          'type': 'function'}]})

        with Transaction().set_user(1):
            self.assertEqual(rule.check_code(), True)

    @test_framework.prepare_test('rule_engine.test0014_testRuleEngineCreation')
    def test0016_testExternalParameterKwarg(self):
        rule = self.RuleEngine.search([('name', '=', 'Test Rule')])[0]
        rule.algorithm = 'return param_test_parameter()'
        rule.save()
        with Transaction().set_user(1):
            self.assertRaises(UserError, rule.check_code)

        kwarg_parameter = self.RuleParameter()
        kwarg_parameter.name = 'test_parameter'
        kwarg_parameter.string = 'Test Parameter'
        kwarg_parameter.type_ = 'boolean'
        kwarg_parameter.parent_rule = rule
        kwarg_parameter.save()
        full_tree_structure = rule.data_tree_structure()
        nbnode = len(full_tree_structure)
        # Parameter node is the third starting from the end
        tree_structure = full_tree_structure[nbnode - 3]
        self.assertEqual(tree_structure, {
            'description': 'Parameters',
            'fct_args': '',
            'long_description': '',
            'name': '',
            'translated': '',
            'type': 'folder',
            'children': [{'children': [],
                          'description': u'Test Parameter',
                          'fct_args': '',
                          'long_description': u'Test Parameter (param)',
                          'name': 'UnusedVariable',
                          'translated': u'param_test_parameter',
                          'type': 'function'}]})

        with Transaction().set_user(1):
            self.assertEqual(rule.check_code(), True)

    @test_framework.prepare_test(
        'rule_engine.test0016_testExternalParameterKwarg')
    def test0017_testExternalParameterRule(self):
        rule = self.RuleEngine.search([('name', '=', 'Test Rule')])[0]
        rule.algorithm = 'return rule_test_rule(test_parameter=True)'
        rule.save()
        with Transaction().set_user(1):
            self.assertRaises(UserError, rule.check_code)

        rule_parameter = self.RuleEngineRuleEngine()
        rule_parameter.rule = rule
        rule_parameter.parent_rule = rule
        rule_parameter.save()

        full_tree_structure = rule.data_tree_structure()
        nbnode = len(full_tree_structure)
        # Parameter node is the third starting from the end
        tree_structure = full_tree_structure[nbnode - 3]
        self.assertEqual(tree_structure, {
            'description': 'Parameters',
            'fct_args': '',
            'long_description': '',
            'name': '',
            'translated': '',
            'type': 'folder',
            'children': [{'children': [],
                          'description': u'Test Parameter',
                          'fct_args': '',
                          'long_description': u'Test Parameter (param)',
                          'name': 'UnusedVariable',
                          'translated': u'param_test_parameter',
                          'type': 'function'}]})
        tree_structure = full_tree_structure[nbnode - 2]
        self.assertEqual(tree_structure, {
            'description': 'Rules',
            'fct_args': '',
            'long_description': '',
            'name': '',
            'translated': '',
            'type': 'folder',
            'children': [{'children': [],
                          'description': u'Test Rule',
                          'fct_args': u'test_parameter=',
                          'long_description': u'Test Rule (rule)',
                          'name': 'UnusedVariable',
                          'translated': u'rule_test_rule',
                          'type': 'function'}]})
        with Transaction().set_user(1):
            self.assertEqual(rule.check_code(), True)

    @test_framework.prepare_test('table.test0060table_2dim',
        'rule_engine.test0014_testRuleEngineCreation')
    def test0020_testAdvancedRule(self):
        rule1 = self.RuleEngine.search([('name', '=', 'Test Rule')])[0]
        table = self.Table.search([('code', '=', 'test_code')])[0]
        kwarg_parameter = self.RuleParameter()
        kwarg_parameter.name = 'test_parameter'
        kwarg_parameter.string = 'Test Parameter'
        kwarg_parameter.parent_rule = rule1
        kwarg_parameter.type_ = 'numeric'
        kwarg_parameter.save()
        rule1.algorithm = 'return param_test_parameter()'
        rule1.status = 'validated'
        rule1.save()

        rule = self.RuleEngine()
        rule.name = 'Test Rule Advanced'
        rule.short_name = 'test_rule_advanced'
        rule.context = rule1.context
        rule_parameter = self.RuleEngineRuleEngine()
        rule_parameter.rule = rule1
        rule_parameter.parent_rule = rule
        rule_parameter.save()
        table_parameter = self.RuleEngineTable()
        table_parameter.table = table
        table_parameter.parent_rule = rule
        table_parameter.save()

        rule.algorithm = '\n'.join([
                "if table_test_code('test', 30):",
                "    return 10",
                "add_error('test error')",
                "add_warning('test warning')",
                "add_info('test info')",
                "if table_test_code('foo', 1) == 'ham':",
                "   return rule_test_rule(test_parameter=20)",
                ])
        rule.status = 'validated'
        rule.save()

    @test_framework.prepare_test('rule_engine.test0020_testAdvancedRule')
    def test0021_testRuleEngineExecution(self):
        rule, = self.RuleEngine.search([('name', '=', 'Test Rule Advanced')])
        result = rule.execute({})
        self.assertEqual(result.result, 20)
        self.assertEqual(result.errors, ['test error'])
        self.assertEqual(result.warnings, ['test warning'])
        self.assertEqual(result.info, ['test info'])
        # Debug mode is not activated => no log
        self.assertEqual(result.low_level_debug, [])
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
                return tcv

            # Check override of table elements
            tcv1 = create_test_case_value('table_test_code', "'something'")
            tc = self.TestCase()
            tc.description = 'Fail Value'
            tc.rule = rule
            tc.test_values = []
            self.maxDiff = None
            tc.on_change_test_values()
            self.assertEqual(tc.low_debug,
                u"Entering table_test_code\n\t"
                "args : ('test', 30)\n\t"
                "result = None\n"
                "Entering add_error\n\t"
                "args : ('test error',)\n\t"
                "result = None\n"
                "Entering add_warning\n\t"
                "args : ('test warning',)\n\t"
                "result = None\n"
                "Entering add_info\n\t"
                "args : ('test info',)\n\t"
                "result = None\n"
                "Entering table_test_code\n\t"
                "args : ('foo', 1)\n\t"
                "result = ham\n"
                "Entering rule_test_rule\n\t"
                "kwargs : {'test_parameter': 20}")
            self.assertEqual(tc.debug, '')
            self.assertEqual(tc.result_errors, u'test error')
            self.assertEqual(tc.expected_result,
                '[20, [test error], [test warning], [test info]]')
            self.assertEqual(tc.result_info, u'test info')
            self.assertEqual(tc.result_value, u'20')
            self.assertEqual(tc.result_warning, u'test warning')
            tc.test_values = [tcv1]
            tc.on_change_test_values()
            self.assertEqual(tc.low_debug,
                u"Entering table_test_code\n\targs : "
                "('test', 30)\n\tresult = something")
            self.assertEqual(tc.result_warning, '')
            self.assertEqual(tc.result_value, u'10')
            self.assertEqual(tc.debug, '')
            self.assertEqual(tc.result_errors, '')
            self.assertEqual(tc.expected_result, '[10, [], [], []]')
            self.assertEqual(tc.result_info, '')
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

    @test_framework.prepare_test('rule_engine.test0030_TestCaseCreation')
    def test0031_TestCaseExportImport(self):
        rule, = self.RuleEngine.search([('name', '=', 'Test Rule Advanced')])
        output = []
        rule.export_json(output=output)
        output[1]['short_name'] = 'test_rule_advanced'
        rule.import_json(output)
        rule_1, = self.RuleEngine.search([
                ('short_name', '=', 'test_rule_advanced')])

        with Transaction().set_context({'active_id': rule_1.id}):
            wizard_id, _, _ = self.RunTests.create()
            wizard = self.RunTests(wizard_id)
            wizard._execute('report')
            res = wizard.default_report(None)
            self.assertEqual(res, {'report':
                    'Fail Value ... SUCCESS\n\n'
                    'Remove Errors ... SUCCESS\n\n'
                    'Override rule ... SUCCESS'})

    @test_framework.prepare_test('rule_engine.test0030_TestCaseCreation')
    def test0032_TestCaseValidation(self):
        rule, = self.RuleEngine.search([('name', '=', 'Test Rule Advanced')])
        assert not rule.passing_test_cases
        self.TestCase.check_pass(list(rule.test_cases))
        assert rule.passing_test_cases
        self.assertEqual(1, len(self.RuleEngine.search([
                        ('id', '=', rule.id),
                        ('passing_test_cases', '=', True)])))
        self.assertEqual(len(rule.test_cases), 3)
        rule.test_cases[0].expected_result = 'monthy'
        self.TestCase.check_pass(list(rule.test_cases))
        assert rule.test_cases[0].last_passing_date is None
        assert rule.test_cases[1].last_passing_date
        assert not rule.passing_test_cases
        self.assertEqual(1, len(self.RuleEngine.search([
                        ('id', '=', rule.id),
                        ('passing_test_cases', '=', False)])))

    @test_framework.prepare_test('rule_engine.test0020_testAdvancedRule')
    def test0060_testRuleEngineDebugging(self):
        # This test must be run later as execute rule with debug enabled forces
        # a commit
        rule, = self.RuleEngine.search([('name', '=', 'Test Rule Advanced')])

        # Check Debug mode
        rule.debug_mode = True
        rule.save()

        Transaction().commit()
        rule.execute({})

        with Transaction().new_transaction():
            self.assertEqual(len(self.Log.search([('rule', '=', rule.id)])), 1)

        # Check execution errors raise UserErrors
        rule.debug_mode = False
        rule.algorithm = 'return rule_test_rule()'
        rule.save()
        self.assertRaises(UserError, rule.execute, {})
        rule.algorithm = 'return 1 / 0'
        rule.save()
        self.assertRaises(UserError, rule.execute, {})

        # Test that disabling debug_mode effectively delete existing logs
        rule.debug_mode = False
        rule.save()
        self.assertEqual(rule.exec_logs, ())

    def test_0061_testTestCaseCreationFromLog(self):
        # test0060 forces a commit so no need for prepare_test
        rule, = self.RuleEngine.search([('name', '=', 'Test Rule Advanced')])
        rule.debug_mode = True
        rule.algorithm = '\n'.join([
                "if table_test_code('test', 30):",
                "    return 10",
                "add_error('test error')",
                "add_warning('test warning')",
                "add_info('test info')",
                "if table_test_code('foo', 1) == 'ham':",
                "   return rule_test_rule(test_parameter=20)",
                ])
        rule.save()

        rule.execute({})
        log = rule.exec_logs[-1]

        with Transaction().set_context({'active_id': log.id,
                    'active_model': 'rule_engine.log',
                    'rule_id': log.rule.id}):
            wizard_id, _, _ = self.InitTestCaseFromExecutionLog.create()
            wizard = self.InitTestCaseFromExecutionLog(wizard_id)
            test_case_dict = wizard.default_select_values(None)
            test_case_dict['description'] = 'Test test case'
            for call in test_case_dict['test_values']:
                if call['name'] in ('add_error', 'add_warning', 'add_info'):
                    call['override_value'] = False
            wizard.execute(wizard_id, {'select_values': test_case_dict},
                'create_test_case')

        with Transaction().set_context({'active_id': rule.id}):
            wizard_id, _, _ = self.RunTests.create()
            wizard = self.RunTests(wizard_id)
            wizard._execute('report')
            res = wizard.default_report(None)
            self.assertEqual(res, {'report':
                    'Test test case ... SUCCESS'})


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite

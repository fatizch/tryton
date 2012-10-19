import sys
import ast
import _ast
import functools
import json
import datetime

from decimal import Decimal

from pyflakes.checker import Checker
from pyflakes.messages import Message, UndefinedName

from trytond.rpc import RPC

from trytond.model import ModelView, ModelSQL, fields
from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from trytond.tools.misc import _compile_source
from trytond.pyson import Eval
from trytond.modules.coop_utils import CoopView, utils as utils
from trytond.modules.coop_utils import date as date
from trytond.modules.table import TableCell

__all__ = ['Rule', 'Context', 'TreeElement', 'ContextTreeElement', 'TestCase',
    'TestCaseValue', 'TestRule', 'TestRuleStart', 'TestRuleTest',
    'CreateTestValues', 'RunTests', 'RunTestsReport', 'RuleTools',
    'RuleEngineContext', 'InternalRuleEngineError', 'check_args',
    'TableDefinition'
    ]

CODE_TEMPLATE = """
def fct_%s():
%%s

result_%s = fct_%s()
"""


def check_code(code):
    try:
        tree = compile(code, 'test', 'exec', _ast.PyCF_ONLY_AST)
    except SyntaxError, syn_error:
        error = Message('test', syn_error.lineno)
        error.message = 'Syntax Error'
        return [error]
    else:
        warnings = Checker(tree, 'test')
        return warnings.messages


class InternalRuleEngineError(Exception):
    pass


def check_args(*_args):
    def decorator(f):
        def wrap(*args, **kwargs):
            f.needed_args = []
            for arg in _args:
                if not arg in args[1]:
                    args[1]['errors'].append('%s undefined !' % arg)
                    raise InternalRuleEngineError
                f.needed_args.append(arg)
            return f(*args, **kwargs)
        wrap.__name__ = f.__name__
        return wrap
    return decorator


def safe_eval(source, data=None):
    if '__subclasses__' in source:
        raise ValueError('__subclasses__ not allowed')

    comp = _compile_source(source)
    return eval(comp, {'__builtins__': {
        'True': True,
        'False': False,
        'str': str,
        'globals': locals,
        'locals': locals,
        'bool': bool,
        'dict': dict,
        'round': round,
        'Decimal': Decimal,
        'datetime': datetime
        }}, data)


def noargs_func(value):
    def newfunc(*args, **keywords):
        return value
    return newfunc


class RuleEngineContext(CoopView):

    @classmethod
    def get_rules(cls):
        res = []
        for elem in dir(cls):
            if not elem.startswith('_re_'):
                continue
            elem = getattr(cls, elem)
            tmpres = {}
            tmpres['name'] = elem.__name__
            res.append(tmpres)
        return res

    @classmethod
    def __setup__(cls):
        super(RuleEngineContext, cls).__setup__()
        cls.__rpc__.update({'get_rules': RPC()})


class RuleTools(RuleEngineContext):
    '''
        Tools functions
    '''
    __name__ = 'rule_engine.tools_functions'

    @classmethod
    def _re_years_between(cls, args, date1, date2):
        if (not isinstance(date1, datetime.date)
                or not isinstance(date2, datetime.date)):
            args['errors'].append('years_between needs datetime types')
            raise InternalRuleEngineError
        return date.number_of_years_between(date1, date2)

    @classmethod
    def _re_today(cls, args):
        return utils.today()

    @classmethod
    def _re_message(cls, args, the_message):
        args['messages'].append(the_message)


class FunctionFinder(ast.NodeVisitor):

    def __init__(self, allowed_names):
        super(FunctionFinder, self).__init__()
        self.functions = set()
        self.allowed_names = allowed_names

    def visit(self, node):
        if isinstance(node, ast.Call):
            if node.func.id not in self.allowed_names:
                raise LookupError(node.func.id)
            self.functions.add(node.func.id)
        return super(FunctionFinder, self).visit(node)


class Rule(ModelView, ModelSQL):
    "Rule"
    __name__ = 'rule_engine'

    name = fields.Char('Name', required=True)
    context = fields.Many2One('rule_engine.context', 'Context',
        on_change=['context'], required=True)
    code = fields.Text('Code')
    data_tree = fields.Function(fields.Text('Data Tree'), 'get_data_tree')
    test_cases = fields.One2Many('rule_engine.test_case', 'rule', 'Test Cases')
    status = fields.Selection([
            ('draft', 'Draft'),
            ('validated', 'Validated'),
            ], 'Status')

    @classmethod
    def __setup__(cls):
        super(Rule, cls).__setup__()
        cls._constraints += [
            ('check_code', 'invalid_code'),
            ]
        cls._error_messages.update({
                'invalid_code': 'Your code has errors!',
                })

    def check_code(self):
        return not bool(filter(
                lambda m: not (isinstance(m, UndefinedName)
                    and m.message_args[0] in self.allowed_functions),
                check_code(self.as_function)))

    @staticmethod
    def default_status():
        return 'draft'

    def compute(self, evaluation_context):
        context = self.context.get_context()
        context.update(evaluation_context)
        context['context'] = context
        localcontext = {}
        try:
            exec self.as_function in context, localcontext
            result = localcontext[('result_%s' %
                    hash(self.name)).replace('-', '_')]
        except InternalRuleEngineError:
            result = None
        except:
            context['errors'].append('Critical Internal Rule Engine Error')
            result = None
        messages = context['messages']
        errors = context['errors']
        return (result, messages, errors)

    def on_change_context(self):
        return {
            'data_tree': self.get_data_tree(None) if self.context else '[]',
            }

    @property
    def as_function(self):
        code = '\n'.join(' ' + l for l in self.code.splitlines())
        name = ('%s' % hash(self.name)).replace('-', '_')
        code_template = CODE_TEMPLATE % (name, name, name)
        return code_template % code

    def get_data_tree(self, name):
        return json.dumps([e.as_tree() for e in self.context.allowed_elements])

    @property
    def allowed_functions(self):
        return sum([e.as_functions_list()
                for e in self.context.allowed_elements], [])

    def get_rec_name(self, name=None):
        return self.name

    @classmethod
    def get_summary(cls, rules, name=None, with_label=True,
                    at_date=None, lang=None):
        res = {}
        for rule in rules:
            kw = 'return'
            pos1 = rule.code.rfind(kw)
            pos2 = rule.code.rfind('\n')
            if pos1 == -1:
                pos1 = 0
            else:
                pos1 += len(kw) + 1
            if pos2 > 0:
                res[rule.id] = rule.code[pos1:pos2]
            else:
                res[rule.id] = rule.name
        return res


class TestCase(ModelView, ModelSQL):
    "Test Case"
    __name__ = 'rule_engine.test_case'
    _rec_name = 'description'

    description = fields.Char('Description', required=True)
    rule = fields.Many2One('rule_engine', 'Rule', required=True,
        ondelete='CASCADE')
    values = fields.One2Many('rule_engine.test_case.value', 'test_case',
        'Values')
    expected_result = fields.Char('Expected Result')

    def do_test(self):
        test_context = {}
        for value in self.values:
            test_context[value.name] = noargs_func(safe_eval(value.value))
        try:
            test_value = self.rule.compute(test_context)
        except InternalRuleEngineError:
            pass
        except:
            return False, sys.exc_info()

        try:
            assert test_value == safe_eval(self.expected_result)
            return True, None
        except AssertionError:
            return False, str(test_value) + ' vs. ' + str(self.expected_result)
        except:
            return False, str(sys.exc_info())


class TestCaseValue(ModelView, ModelSQL):
    "Test Case Value"
    __name__ = 'rule_engine.test_case.value'

    name = fields.Char('Name')
    value = fields.Char('Value')
    test_case = fields.Many2One('rule_engine.test_case', 'Test Case',
        ondelete='CASCADE')


class Context(ModelView, ModelSQL):
    "Context"
    __name__ = 'rule_engine.context'

    name = fields.Char('Name', required=True)
    allowed_elements = fields.Many2Many(
        'rule_engine.context-rule_engine.tree_element', 'context',
        'tree_element', 'Allowed tree elements')

    @classmethod
    def __setup__(cls):
        super(Context, cls).__setup__()
        cls._constraints += [
            ('check_duplicate_name', 'duplicate_name'),
            ]
        cls._error_messages.update({
                'duplicate_name': 'You define twice the same name!',
                })

    def check_duplicate_name(self):
        names = set()
        elements = list(self.allowed_elements)
        while elements:
            element = elements.pop()
            if element.translated_technical_name in names:
                return False
            else:
                names.add(element.translated_technical_name)
            elements.extend(element.children)
        return True

    def get_context(self):
        context = {}
        context['messages'] = []
        context['errors'] = []
        for element in self.allowed_elements:
            element.as_context(context)
        return context


class TreeElement(ModelView, ModelSQL):
    "Rule Engine Tree Element"
    __name__ = 'rule_engine.tree_element'
    _rec_name = 'description'

    description = fields.Char('Description',
        on_change=['description', 'translated_technical_name'])
    rule = fields.Many2One('rule_engine', 'Rule', states={
            'invisible': Eval('type') != 'rule',
            'required': Eval('type') == 'rule',
            }, depends=['rule'])
    name = fields.Char('Name', states={
            'invisible': ~Eval('type').in_(['function']),
            'required': Eval('type').in_(['function']),
            }, depends=['type'])
    namespace = fields.Char('Namespace', states={
            'invisible': Eval('type') != 'function',
            'required': Eval('type') == 'function',
            }, depends=['type'])
    type = fields.Selection([
            ('folder', 'Folder'),
            ('function', 'Function'),
            ('rule', 'Rule'),
            ('table', 'Table'),
            ], 'Type', required=True)
    parent = fields.Many2One('rule_engine.tree_element', 'Parent')
    children = fields.One2Many('rule_engine.tree_element', 'parent',
        'Children')
    translated_technical_name = fields.Char('Translated technical name',
        states={
            'invisible': ~Eval('type').in_(['function', 'rule']),
            'required': Eval('type').in_(['function', 'rule']),
            }, depends=['type'])
    language = fields.Many2One('ir.lang', 'Language', required=True)
    the_table = fields.Many2One(
        'table.table_def',
        'For Table',
        states={
            'invisible': Eval('type') != 'table',
            'required': Eval('type') == 'table'},
        on_change=['translated_technical_name', 'description', 'the_table'],
        ondelete='RESTRICT')

    @staticmethod
    def default_type():
        return 'function'

    def on_change_description(self):
        if self.translated_technical_name:
            return {}
        return {
            'translated_technical_name': self.description.replace(' ', '_'),
            }

    def on_change_the_table(self):
        if not(hasattr(self, 'the_table') and self.the_table):
            return {}
        return {
            'translated_technical_name': 'table_%s' % self.the_table.code,
            'description': 'Table %s' % self.the_table.name}

    def as_tree(self):
        tree = {}
        tree['name'] = self.name
        tree['translated'] = self.translated_technical_name
        tree['description'] = self.description
        tree['type'] = self.type
        tree['children'] = [child.as_tree() for child in self.children]
        return tree

    def as_functions_list(self):
        if self.type in ('function', 'rule', 'table'):
            return [self.translated_technical_name]
        else:
            return sum([child.as_functions_list()
                    for child in self.children], [])

    def as_context(self, context):
        pool = Pool()
        if self.type == 'function':
            namespace_obj = pool.get(self.namespace)
            context[self.translated_technical_name] = functools.partial(
                getattr(namespace_obj, self.name), context)
        elif self.type == 'rule':
            context[self.translated_technical_name] = functools.partial(
                self.rule.compute, context)
        elif self.type == 'table':
            context[self.translated_technical_name] = functools.partial(
                TableCell.get, self.the_table)
        for element in self.children:
            element.as_context(context)
        return context


class ContextTreeElement(ModelSQL):
    "Context Tree Element"
    __name__ = 'rule_engine.context-rule_engine.tree_element'

    context = fields.Many2One('rule_engine.context', 'Context', required=True,
        ondelete='CASCADE')
    tree_element = fields.Many2One('rule_engine.tree_element', 'Tree Element',
        required=True, ondelete='CASCADE')


class TestRuleStart(ModelView):
    "Test Rule Input Form"
    __name__ = 'rule_engine.test_rule.start'

    context = fields.Text('Context')


class TestRuleTest(ModelView):
    "Test Rule Result Form"
    __name__ = 'rule_engine.test_rule.test'

    result = fields.Text('Result')


class TestRule(Wizard):
    "Test Rule Wizard"
    __name__ = 'rule_engine.test_rule'

    start = StateView('rule_engine.test_rule.start',
        'rule_engine.test_rule_start_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Test', 'test', 'tryton-go-next', True)
            ])
    test = StateView('rule_engine.test_rule.test',
        'rule_engine.test_rule_test_form', [
            Button('OK', 'end', 'tryton-ok', True),
            ])

    def default_start(self, fields):
        return {}

    def default_test(self, fields):
        Rule = Pool().get('rule_engine')

        context = eval(self.start.context)
        rule = Rule(Transaction().context['active_id'])
        return {
            'result': str(rule.compute(context)),
            }


class RunTestsReport(ModelView):
    "Test Run Report"
    __name__ = 'rule_engine.run_tests.report'

    report = fields.Text('Report', readonly=True)


class RunTests(Wizard):
    "Run the test cases"
    __name__ = 'rule_engine.run_tests'
    start_state = 'report'

    report = StateView('rule_engine.run_tests.report',
        'rule_engine.run_tests_report', [
            Button('OK', 'end', 'tryton-ok', True),
            ])

    def format_result(self, test_case):
        success, info = test_case.do_test()
        if success:
            return '{} ... SUCCESS'.format(test_case.description)
        else:
            return '{} ... FAILED'.format(test_case.description) +\
                '\n%s' % str(info)

    def default_report(self, fields):
        Rule = Pool().get('rule_engine')
        rule = Rule(Transaction().context['active_id'])
        results = []
        for test_case in rule.test_cases:
            results.append(self.format_result(test_case))

        return {
            'report': '\n\n'.join(results),
            }


class CreateTestValues(Wizard):
    "Create Test Values Wizard"
    __name__ = 'rule_engine.create_test_values'

    start = StateTransition()

    def transition_start(self):
        TestCase = Pool().get('rule_engine.test_case')
        TestCaseValue = Pool().get('rule_engine.test_case.value')

        test_case = TestCase(Transaction().context['active_id'])
        func_values = set(v.name for v in test_case.values)
        func_finder = FunctionFinder([test_case.rule.name]
            + test_case.rule.allowed_functions)
        ast_node = ast.parse(test_case.rule.as_function)
        func_finder.visit(ast_node)
        for func_name in func_finder.functions:
            if func_name == test_case.rule.name or func_name in func_values:
                continue
            test_value = TestCaseValue(name=func_name, test_case=test_case)
            test_value.save()
        return 'end'


class TableDefinition():
    'Table Definition'

    __metaclass__ = PoolMeta

    __name__ = 'table.table_def'

    @classmethod
    def create(cls, values):
        table = super(TableDefinition, cls).create(values)
        TreeElement = Pool().get('rule_engine.tree_element')
        folder = utils.get_those_objects(
            'rule_engine.tree_element',
            [('type', '=', 'folder'), ('description', '=', 'Tables')])
        if not folder:
            folder = TreeElement()
            folder.type = 'folder'
            folder.description = 'Tables'
            folder.translated_technical_name = 'table_folder'
            folder.language = utils.get_this_object(
                'ir.lang', ('code', '=', Transaction().language))
            folder.save()
        else:
            folder = folder[0]

        new_tree = TreeElement()
        new_tree.type = 'table'
        new_tree.translated_technical_name = 'table_%s' % values['code']
        new_tree.description = 'Table %s' % values['name']
        new_tree.language = utils.get_this_object(
            'ir.lang', ('code', '=', Transaction().language))
        new_tree.the_table = table.id
        new_tree.parent = folder
        new_tree.save()
        return table

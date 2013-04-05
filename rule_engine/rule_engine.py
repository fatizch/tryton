import sys
import ast
import _ast
import tokenize
import functools
import json
import datetime
from StringIO import StringIO

from decimal import Decimal

from pyflakes.checker import Checker
import pyflakes.messages

from trytond.rpc import RPC

from trytond.modules.coop_utils import fields
from trytond.modules.coop_utils.model import CoopSQL as ModelSQL
from trytond.modules.coop_utils.model import CoopView as ModelView
from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from trytond.tools.misc import _compile_source
from trytond.pyson import Eval, And
from trytond.modules.coop_utils import CoopView, utils, coop_string
from trytond.modules.coop_utils import date
from trytond.modules.table import TableCell

__all__ = [
    'Rule', 'Context', 'TreeElement', 'ContextTreeElement', 'TestCase',
    'TestCaseValue', 'TestRule', 'TestRuleStart', 'TestRuleTest',
    'CreateTestValues', 'RunTests', 'RunTestsReport', 'RuleTools',
    'RuleEngineContext', 'InternalRuleEngineError', 'check_args',
    'CreateTestCase', 'CreateTestCaseStart', 'CreateTestCaseAskDescription',
    'TableDefinition'
]

CODE_TEMPLATE = """
def fct_%s():
 from decimal import Decimal
%%s

result_%s = fct_%s()
"""


def check_code(code):
    try:
        tree = compile(code, 'test', 'exec', _ast.PyCF_ONLY_AST)
    except SyntaxError, syn_error:
        error = pyflakes.messages.Message('test', syn_error.lineno)
        error.message = 'Syntax Error'
        return [error]
    else:
        warnings = Checker(tree, 'test')
        return warnings.messages

WARNINGS = []
for name in (
        'UnusedImport', 'RedefinedWhileUnused', 'ImportShadowedByLoopVar',
        'ImportStarUsed', 'UndefinedExport', 'RedefinedFunction',
        'LateFutureImport', 'UnusedVariable'):
    message = getattr(pyflakes.messages, name, None)
    if message is not None:
        WARNINGS.append(message)
WARNINGS = tuple(WARNINGS)


# code snippet taken from http://docs.python.org/library/tokenize.html
def decistmt(s):
    """Substitute Decimals for floats in a string of statements.

    >>> from decimal import Decimal
    >>> s = 'print +21.3e-5*-.1234/81.7'
    >>> decistmt(s)
    "print +Decimal ('21.3e-5')*-Decimal ('.1234')/Decimal ('81.7')"

    >>> exec(s)
    -3.21716034272e-007
    >>> exec(decistmt(s))
    -3.217160342717258261933904529E-7
    """
    result = []
    # tokenize the string
    g = tokenize.generate_tokens(StringIO(s).readline)
    for toknum, tokval, _, _, _ in g:
        # replace NUMBER tokens
        if toknum == tokenize.NUMBER and '.' in tokval:
            result.extend([
                (tokenize.NAME, 'Decimal'),
                (tokenize.OP, '('),
                (tokenize.STRING, repr(tokval)),
                (tokenize.OP, ')')
            ])
        else:
            result.append((toknum, tokval))
    return tokenize.untokenize(result)


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
    return eval(comp, {
        '__builtins__': {
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


def noargs_func(values):
    v_iterator = iter(values)

    def newfunc(*args, **keywords):
        return v_iterator.next()

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
        args['messages'].append(str(the_message))

    @classmethod
    def _re_debug(cls, args, the_message):
        if Transaction().context.get('debug'):
            args['debug'].append(str(the_message))

    @classmethod
    def _re_calculation_date(cls, args):
        return args['date'] if 'date' in args else cls._re_today(args)


class FunctionFinder(ast.NodeVisitor):

    def __init__(self, allowed_names):
        super(FunctionFinder, self).__init__()
        self.functions = []
        self.allowed_names = allowed_names

    def visit(self, node):
        if (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)):
            if node.func.id not in self.allowed_names:
                raise LookupError(node.func.id)
            self.functions.append(node.func.id)
        return super(FunctionFinder, self).visit(node)


class Rule(ModelView, ModelSQL):
    "Rule"
    __name__ = 'rule_engine'

    name = fields.Char('Name', required=True)
    context = fields.Many2One(
        'rule_engine.context', 'Context', on_change=['context'], required=True)
    code = fields.Text('Code')
    data_tree = fields.Function(fields.Text('Data Tree'), 'get_data_tree')
    test_cases = fields.One2Many('rule_engine.test_case', 'rule', 'Test Cases')
    status = fields.Selection(
        [
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

    @classmethod
    def _export_keys(cls):
        return set(['name'])

    def filter_errors(self, error):
        if isinstance(error, WARNINGS):
            return False
        elif (isinstance(error, pyflakes.messages.UndefinedName)
                and error.message_args[0] in self.allowed_functions):
            return False
        else:
            return True

    def check_code(self):
        return not bool(filter(
            lambda m: self.filter_errors(m),
            check_code(self.as_function)))

    @staticmethod
    def default_status():
        return 'draft'

    def get_context_for_execution(self):
        return self.context.get_context()

    def compute(self, evaluation_context, debug_mode=False):
        with Transaction().set_context(debug=debug_mode):
            context = self.get_context_for_execution()
            context.update(evaluation_context)
            context['context'] = context
            localcontext = {}
            try:
                exec self.as_function in context, localcontext
                result = localcontext[
                    ('result_%s' % hash(self.name)).replace('-', '_')]
            except:
                # raise
                context['errors'].append(
                    'Critical Internal Rule Engine Error in rule %s' % self.name)
                result = None

        messages = context['messages']
        errors = context['errors']
        if debug_mode:
            debug = context['debug']
            return (result, messages, errors, debug)
        else:
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
        return decistmt(code_template % code)

    def get_data_tree(self, name):
        return json.dumps([e.as_tree() for e in self.context.allowed_elements])

    @property
    def allowed_functions(self):
        return sum([
            e.as_functions_list() for e in self.context.allowed_elements], [])

    def get_rec_name(self, name=None):
        return self.name


class TestCase(ModelView, ModelSQL):
    "Test Case"
    __name__ = 'rule_engine.test_case'
    _rec_name = 'description'

    description = fields.Char('Description', required=True)
    rule = fields.Many2One(
        'rule_engine', 'Rule', required=True,
        ondelete='CASCADE', context={'rule_id': Eval('rule')})
    values = fields.One2Many(
        'rule_engine.test_case.value', 'test_case', 'Values')
    expected_result = fields.Char('Expected Result')

    def do_test(self):
        test_context = {}
        for value in self.values:
            test_context.setdefault(value.name, []).append(
                safe_eval(value.value))
        test_context = {
            key: noargs_func(value) for key, value in test_context.items()}
        try:
            test_value = self.rule.compute(test_context)
            for key, noargs in test_context.iteritems():
                try:
                    noargs()
                except StopIteration:
                    pass
                else:
                    raise TypeError('Too few calls to {}'.format(key))
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

    name = fields.Selection(
        'get_selection', 'Name',
        selection_change_with=['rule'], depends=['rule'])
    value = fields.Char('Value')
    test_case = fields.Many2One(
        'rule_engine.test_case', 'Test Case', ondelete='CASCADE')
    rule = fields.Function(
        fields.Many2One(
            'rule_engine',
            'Rule',
        ),
        'get_rule',
    )

    @classmethod
    def __setup__(cls):
        super(TestCaseValue, cls).__setup__()
        cls.__rpc__.update({
            'get_selection': RPC(instantiate=0),
        })

    def get_rule(self, name):
        if (hasattr(self, 'test_case') and self.test_case) and (
                hasattr(self.test_case, 'rule') and self.test_case.rule):
            return self.test_case.rule.id
        elif 'rule_id' in Transaction().context:
            return Transaction().context.get('rule_id')
        else:
            return None

    @classmethod
    def default_rule(cls):
        if 'rule_id' in Transaction().context:
            return Transaction().context.get('rule_id')
        else:
            return None

    def get_selection(self):
        if not (hasattr(self, 'rule') and self.rule):
            return [('', '')]
        rule = self.rule
        rule_name = ('fct_%s' % hash(rule.name)).replace('-', '_')
        func_finder = FunctionFinder(
            ['Decimal', rule_name] + rule.allowed_functions)
        ast_node = ast.parse(rule.as_function)
        func_finder.visit(ast_node)
        test_values = list(set([
            (n, n) for n in func_finder.functions
            if n not in (rule_name, 'Decimal')]))
        return test_values + [('', '')]


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
        context['debug'] = []
        for element in self.allowed_elements:
            element.as_context(context)
        return context


class TreeElement(ModelView, ModelSQL):
    "Rule Engine Tree Element"
    __name__ = 'rule_engine.tree_element'
    _rec_name = 'description'

    description = fields.Char(
        'Description', on_change=['description', 'translated_technical_name'])
    rule = fields.Many2One(
        'rule_engine', 'Rule', states={
            'invisible': Eval('type') != 'rule',
            'required': Eval('type') == 'rule',
        }, depends=['rule'])
    name = fields.Char(
        'Name', states={
            'invisible': ~Eval('type').in_(['function']),
            'required': Eval('type').in_(['function']),
        }, depends=['type'])
    namespace = fields.Char(
        'Namespace', states={
            'invisible': Eval('type') != 'function',
            'required': Eval('type') == 'function',
        }, depends=['type'])
    type = fields.Selection(
        [
            ('folder', 'Folder'),
            ('function', 'Function'),
            ('rule', 'Rule'),
            ('table', 'Table'),
        ], 'Type', required=True)
    parent = fields.Many2One('rule_engine.tree_element', 'Parent')
    children = fields.One2Many(
        'rule_engine.tree_element', 'parent', 'Children')
    translated_technical_name = fields.Char(
        'Translated technical name',
        states={
            'invisible': ~Eval('type').in_(['function', 'rule', 'table']),
            'required': Eval('type').in_(['function', 'rule', 'table']),
        }, depends=['type'],
        on_change_with=['rule'])
    fct_args = fields.Char(
        'Function Arguments', states={
            'invisible': And(
                Eval('type') != 'function',
                Eval('type') != 'table'
            ),
        })
    language = fields.Many2One('ir.lang', 'Language', required=True)
    the_table = fields.Many2One(
        'table.table_def',
        'For Table',
        states={
            'invisible': Eval('type') != 'table',
            'required': Eval('type') == 'table'},
        on_change=['translated_technical_name', 'description', 'the_table'],
        ondelete='CASCADE')
    long_description = fields.Text('Long Description')

    @classmethod
    def __setup__(cls):
        super(TreeElement, cls).__setup__()
        cls._constraints.extend([
            ('check_arguments_accents', 'argument_accent_error'),
            ('check_name_accents', 'name_accent_error')])
        cls._error_messages.update({
            'argument_accent_error': 'Function arguments must only use ascii',
            'name_accent_error': 'Technical name must only use ascii',
        })

    @classmethod
    def _export_keys(cls):
        return set(['type', 'translated_technical_name', 'language.code'])

    @classmethod
    def _export_force_recreate(cls):
        result = super(TreeElement, cls)._export_force_recreate()
        result.remove('children')
        return result

    def check_arguments_accents(self):
        if not self.fct_args:
            return True
        return coop_string.is_ascii(self.fct_args)

    def check_name_accents(self):
        if not self.name:
            return True
        return coop_string.is_ascii(self.translated_technical_name)

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
        tree['fct_args'] = self.fct_args if self.fct_args else ''
        tree['description'] = self.description
        tree['type'] = self.type
        tree['children'] = [child.as_tree() for child in self.children]
        tree['long_description'] = self.long_description
        return tree

    def as_functions_list(self):
        if self.type in ('function', 'rule', 'table'):
            return [self.translated_technical_name]
        else:
            return sum([
                child.as_functions_list() for child in self.children], [])

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

    def on_change_with_translated_technical_name(self):
        if self.rule:
            return coop_string.remove_blank_and_invalid_char(self.rule.name)

    @staticmethod
    def default_long_description():
        return ''


class ContextTreeElement(ModelSQL):
    "Context Tree Element"
    __name__ = 'rule_engine.context-rule_engine.tree_element'

    context = fields.Many2One(
        'rule_engine.context', 'Context', required=True, ondelete='CASCADE')
    tree_element = fields.Many2One(
        'rule_engine.tree_element', 'Tree Element',
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

    start = StateView(
        'rule_engine.test_rule.start',
        'rule_engine.test_rule_start_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Test', 'test', 'tryton-go-next', True)
        ])
    test = StateView(
        'rule_engine.test_rule.test',
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

    report = StateView(
        'rule_engine.run_tests.report',
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
        func_finder = FunctionFinder(
            [test_case.rule.name] + test_case.rule.allowed_functions)
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
    def get_or_create_table_folder(cls):
        TreeElement = Pool().get('rule_engine.tree_element')
        good_language, = utils.get_this_object(
            'ir.lang', ('code', '=', Transaction().language))
        folder, = utils.get_those_objects(
            'rule_engine.tree_element',
            [('type', '=', 'folder'), ('description', '=', 'Tables'),
                ('language', '=', good_language)])
        if not folder:
            folder = TreeElement()
            folder.type = 'folder'
            folder.description = 'Tables'
            folder.translated_technical_name = 'table_folder'
            folder.language = good_language
            folder.save()
        else:
            folder = folder[0]

        return folder

    def get_good_tree_element(self):
        TreeElement = Pool().get('rule_engine.tree_element')
        good_language = utils.get_this_object(
            'ir.lang', ('code', '=', Transaction().language))
        return utils.get_those_objects(
            TreeElement.__name__,
            [('the_table', '=', self), ('language', '=', good_language)])[0]

    @classmethod
    def write(cls, tables, values):
        super(TableDefinition, cls).write(tables, values)

        if not ('dimension_name1' in values or 'dimension_name2' in values or
                'dimension_name3' in values or 'dimension_name4' in values):
            return

        if '__importing__' in Transaction().context:
            return

        dimension_names = []
        for table in tables:
            good_te = table.get_good_tree_element()
            for idx in (1, 2, 3, 4):
                try:
                    dim = getattr(table, 'dimension_kind%s' % idx)
                except AttributeError:
                    break
                if not dim:
                    break

                try:
                    dim_name = getattr(table, 'dimension_name%s' % idx)
                except AttributeError:
                    dim_name = 'Col #%s' % idx

                dimension_names.append(dim_name)

            good_te.fct_args = ', '.join(
                map(coop_string.remove_invalid_char, dimension_names))
            good_te.save()

    @classmethod
    def create(cls, values):
        tables = super(TableDefinition, cls).create(values)
        if '__importing__' in Transaction().context:
            return tables
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

        for table in tables:
            new_tree = TreeElement()
            new_tree.type = 'table'
            if not 'TABLE' in table.code.upper():
                new_tree.translated_technical_name = 'table_%s' % table.code
            else:
                new_tree.translated_technical_name = table.code
            if not 'TABLE' in table.name.upper():
                new_tree.description = 'Table %s' % table.name
            else:
                new_tree.description = table.name
            new_tree.language = utils.get_this_object(
                'ir.lang', ('code', '=', Transaction().language))
            new_tree.the_table = table.id
            new_tree.parent = folder
            dimension_names = []
            for idx in (1, 2, 3, 4):
                try:
                    dim = getattr(table, 'dimension_kind%s' % idx)
                except AttributeError:
                    break
                if not dim:
                    break

                try:
                    dim_name = getattr(table, 'dimension_name%s' % idx)
                except AttributeError:
                    dim_name = None
                if not dim_name:
                    dim_name = 'Col #%s' % idx

                dimension_names.append(dim_name)

            if dimension_names:
                new_tree.fct_args = ', '.join(
                    map(coop_string.remove_invalid_char, dimension_names))
            new_tree.save()

        return tables


class CreateTestCaseStart(ModelView):
    'Display test cases variables'
    __name__ = 'rule_engine.create_test_case.start'

    rule = fields.Many2One('rule_engine', 'Rule', readonly=True)
    unknown_values = fields.Integer('Unknown Values')
    test_values = fields.One2Many(
        'rule_engine.test_case.value', None,
        'Values', size=Eval('unknown_values', 0),
        on_change=['test_values', 'rule'], depends=['unknown_values', 'rule'],
        context={'rule_id': Eval('rule')})
    result_value = fields.Char('Result Value', readonly=True)
    result_messages = fields.Text('Result Messages', readonly=True)
    result_errors = fields.Text('Result Errors', readonly=True)
    debug = fields.Text('Debug Info', readonly=True)

    def on_change_test_values(self):
        test_context = {}
        for value in self.test_values:
            val = safe_eval(value.value if value.value != '' else "''")
            test_context.setdefault(value.name, []).append(val)
        test_context = {
            key: noargs_func(value) for key, value in test_context.items()}
        try:
            test_value = self.rule.compute(test_context, debug_mode=True)
            result_value = str(test_value[0])
            result_messages, result_errors, debug = test_value[1:]
        except Exception as exc:
            result_value = 'ERROR: {}'.format(exc)
            return {
                'result_value': result_value,
                'result_messages': '',
                'result_errors': '',
                'debug': '',
            }
        return {
            'result_value': result_value,
            'result_messages': '\n'.join(result_messages),
            'result_errors': '\n'.join(result_errors),
            'debug': '\n'.join(debug),
        }


class CreateTestCaseAskDescription(ModelView):
    'Ask for test case description'
    __name__ = 'rule_engine.create_test_case.ask_description'

    description = fields.Char('Description', required=True)


class CreateTestCase(Wizard):
    'Create a test case'
    __name__ = 'rule_engine.create_test_case'

    start = StateView(
        'rule_engine.create_test_case.start',
        'rule_engine.create_test_case_start_view', [
            Button('Create Test Case', 'ask_description', default=True),
            Button('Cancel', 'end'),
        ])
    ask_description = StateView(
        'rule_engine.create_test_case.ask_description',
        'rule_engine.create_test_case_ask_description', [
            Button('Create', 'create_test_case', default=True),
            Button('Cancel', 'end'),
        ])
    create_test_case = StateTransition()

    def default_start(self, fields):
        return {
            'rule': Transaction().context['active_id'],
        }

    def compute_value(self):
        Rule = Pool().get('rule_engine')
        rule, = Rule.browse([Transaction().context['active_id']])
        test_context = {}
        for value in self.start.test_values:
            val = safe_eval(value.value)
            test_context.setdefault(value.name, []).append(val)
        test_context = {
            key: noargs_func(value) for key, value in test_context.items()}
        return rule.compute(test_context)

    def transition_create_test_case(self):
        testcase = Pool().get('rule_engine.test_case')
        testcase.create([{
            'description': self.ask_description.description,
            'rule': Transaction().context['active_id'],
            'values': [
                ('create', [{'name': tv.name, 'value': tv.value}])
                for tv in self.start.test_values],
            'expected_result': str(self.compute_value()),
        }])
        return 'end'

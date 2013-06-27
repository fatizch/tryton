import sys
import traceback
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

from trytond.exceptions import UserError
from trytond.modules.coop_utils import fields
from trytond.modules.coop_utils.model import CoopSQL as ModelSQL
from trytond.modules.coop_utils.model import CoopView as ModelView
from trytond.wizard import Wizard, StateView, Button
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from trytond.tools.misc import _compile_source
from trytond.pyson import Eval, And
from trytond.modules.coop_utils import model, CoopView, utils, coop_string
from trytond.modules.coop_utils import date
from trytond.modules.table import TableCell

__all__ = [
    'Rule',
    'RuleEngineParameter',
    'RuleExecutionLog',
    'Context',
    'TreeElement',
    'ContextTreeElement',
    'TestCase',
    'TestCaseValue',
    'RunTests',
    'RunTestsReport',
    'RuleTools',
    'RuleEngineContext',
    'InternalRuleEngineError',
    'CatchedRuleEngineError',
    'check_args',
    'TableDefinition',
    'RuleError',
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
    'Substitute Decimals for floats in a string of statements.'
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


def check_args(*_args):
    def decorator(f):
        def wrap(*args, **kwargs):
            f.needed_args = []
            for arg in _args:
                if not arg in args[1]:
                    args[1]['__result__'].errors.append('%s undefined !' % arg)
                    raise CatchedRuleEngineError
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


def noargs_func(name, values):
    v_iterator = iter(values)

    def newfunc(*args, **keywords):
        try:
            return v_iterator.next()
        except StopIteration:
            raise TooManyFunctionCall('Too many calls to {}'.format(name))

    return newfunc


class InternalRuleEngineError(Exception):
    pass


class CatchedRuleEngineError(Exception):
    pass


class TooManyFunctionCall(StopIteration):
    pass


class TooFewFunctionCall(Exception):
    pass


class RuleEngineResult(object):
    'Rule engine result'

    def __init__(self):
        super(RuleEngineResult, self).__init__()
        self.errors = []
        self.warnings = []
        self.info = []
        self.debug = []
        self.low_level_debug = []
        self.result = None
        self.result_set = False

    @property
    def has_errors(self):
        return bool(self.errors)

    def __str__(self):
        return '[' + ', '.join(map(str, [
            self.result, self.errors, self.warnings, self.info])) + ']'

    def print_errors(self):
        return map(str, self.errors)

    def print_warnings(self):
        return map(str, self.warnings)

    def print_info(self):
        return map(str, self.info)

    def print_debug(self):
        return map(str, self.debug)

    def print_result(self):
        return str(self.result)


class RuleExecutionLog(ModelSQL, ModelView):
    'Rule Execution Log'

    __name__ = 'rule_engine.execution_log'

    user = fields.Many2One('res.user', 'User')
    rule = fields.Many2One('rule_engine', 'Rule', ondelete='CASCADE')
    errors = fields.Text('Errors', states={'readonly': True})
    warnings = fields.Text('Warnings', states={'readonly': True})
    info = fields.Text('Info', states={'readonly': True})
    debug = fields.Text('Debug', states={'readonly': True})
    low_level_debug = fields.Text('Execution Trace', states={'readonly': True})
    result = fields.Char('Result', states={'readonly': True})

    def init_from_rule_result(self, result):
        self.errors = '\n'.join(result.print_errors())
        self.warnings = '\n'.join(result.print_warnings())
        self.info = '\n'.join(result.print_info())
        self.debug = '\n'.join(result.print_debug())
        self.low_level_debug = '\n'.join(result.low_level_debug)
        self.result = result.print_result()


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

    @classmethod
    def get_result(cls, args):
        if '__result__' in args:
            return args['__result__']
        raise InternalRuleEngineError('Result not found')

    @classmethod
    def append_error(cls, args, error_msg):
        cls.get_result(args).errors.append(error_msg)


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
            raise CatchedRuleEngineError
        return date.number_of_years_between(date1, date2)

    @classmethod
    def _re_today(cls, args):
        return utils.today()

    @classmethod
    def add_error(cls, args, error_code, custom=False, lvl=None):
        RuleError = Pool().get('rule_engine.error')
        if custom:
            error = error_code
        else:
            error = RuleError.search([('code', '=', error_code)])
            if len(error) < 1:
                cls.get_result(args).errors.append(
                    'No error definition found for error_code %s' % error_code)
                raise CatchedRuleEngineError
            elif len(error) > 1:
                cls.get_result(args).errors.append(
                    'Multiple definitions for error code : %s' % error_code)
                raise CatchedRuleEngineError
            error = error[0]
            lvl = error.kind
        if lvl == 'info':
            cls.get_result(args).info.append(error)
        elif lvl == 'warning':
            cls.get_result(args).warnings.append(error)
        elif lvl == 'error':
            cls.get_result(args).errors.append(error)

    @classmethod
    def _re_add_error(cls, args, error_message):
        cls.add_error(args, error_message, custom=True, lvl='error')

    @classmethod
    def _re_add_warning(cls, args, error_message):
        cls.add_error(args, error_message, custom=True, lvl='warning')

    @classmethod
    def _re_add_info(cls, args, error_message):
        cls.add_error(args, error_message, custom=True, lvl='info')

    @classmethod
    def _re_add_error_code(cls, args, error_code):
        cls.add_error(args, error_code)

    @classmethod
    def _re_debug(cls, args, the_message):
        cls.get_result(args).debug.append(str(the_message))

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


class RuleEngineParameter(ModelView, ModelSQL):
    'Rule Engine Parameter'

    __name__ = 'rule_engine.parameter'

    name = fields.Char('Name')
    code = fields.Char('Code', required=True)
    kind = fields.Selection([('rule', 'Rule'), ('kwarg', 'Keyword Argument')],
        'Kind', on_change=['kind'])
    the_rule = fields.Many2One('rule_engine', 'Rule to use', states={
            'invisible': Eval('kind', '') != 'rule',
            'required': Eval('kind', '') == 'rule'},
        ondelete='RESTRICT')
    parent_rule = fields.Many2One('rule_engine', 'Parent Rule', required=True,
        ondelete='CASCADE')

    @classmethod
    def __setup__(cls):
        super(RuleEngineParameter, cls).__setup__()
        cls._error_messages.update({
            'kwarg_expected': 'Expected %s as a parameter for rule %s',
        })

    def on_change_kind(self):
        if (hasattr(self, 'kind') and self.kind != 'rule'):
            return {'the_rule': None}
        return {}

    def get_fct_args(self):
        if self.kind == 'rule':
            if not (hasattr(self, 'the_rule') and self.the_rule):
                return ''
            return ', '.join(('%s=' % elem.code for elem in
                    self.the_rule.rule_parameters if elem.kind == 'kwarg'))
        return ''

    def get_description(self):
        return (self.name if self.name else '') + ' (' + (
            self.kind if self.kind else '') + ')'

    def get_long_description(self):
        return self.get_description()

    def get_translated_technical_name(self):
        return 'rule_engine_parameter_%s' % self.code

    def execute_rule(self, evaluation_context, **kwargs):
        result = utils.execute_rule(self, self.the_rule, evaluation_context,
            **kwargs)
        if result.has_errors:
            raise InternalRuleEngineError(
                'Impossible to evaluate parameter %s when computing rule %s' %
                (self.code, self.parent_rule.name))
        return result.result

    def get_wrapper_func(self, context):
        def debug_wrapper(func):
            def wrapper_func(*args, **kwargs):
                context['__result__'].low_level_debug.append(
                    'Entering %s (args = %s)' % (
                        self.get_translated_technical_name(), str(args)))
                try:
                    result = func(*args, **kwargs)
                except Exception, exc:
                    context['__result__'].errors.append(
                        'Error in %s : %s' % (
                            self.get_translated_technical_name(), str(exc)))
                    raise
                context['__result__'].low_level_debug.append(
                    'Exiting %s (result = %s)' % (
                        self.get_translated_technical_name(), str(result)))
                return result
            return wrapper_func
        return debug_wrapper

    def as_context(self, evaluation_context, context, forced_value):
        debug_wrapper = self.get_wrapper_func(context)
        if not forced_value:
            if self.kind == 'kwarg':
                self.raise_user_error('kwarg_expected', (self.code,
                        self.parent_rule.name))
        if forced_value:
            context[self.get_translated_technical_name()] = debug_wrapper(
                lambda: forced_value)
        elif self.kind == 'rule':
            context[self.get_translated_technical_name()] = debug_wrapper(
                functools.partial(self.execute_rule, evaluation_context))
        return context


class Rule(ModelView, ModelSQL):
    "Rule"
    __name__ = 'rule_engine'

    name = fields.Char('Name', required=True)
    context = fields.Many2One(
        'rule_engine.context', 'Context', on_change=['context',
            'rule_parameters'], required=True)
    code = fields.Text('Code')
    data_tree = fields.Function(fields.Text('Data Tree'), 'get_data_tree')
    test_cases = fields.One2Many(
        'rule_engine.test_case', 'rule', 'Test Cases',
        states={'invisible': Eval('id', 0) <= 0},
        context={'rule_id': Eval('id')})
    status = fields.Selection(
        [
            ('draft', 'Draft'),
            ('validated', 'Validated'),
        ], 'Status')
    debug_mode = fields.Boolean('Debug Mode')
    exec_logs = fields.One2Many(
        'rule_engine.execution_log', 'rule', 'Execution Logs',
        states={'readonly': True, 'invisible': ~Eval('debug_mode')},
        depends=['debug_mode'])
    rule_parameters = fields.One2Many('rule_engine.parameter', 'parent_rule',
        'Rule parameters', on_change=['rule_parameters', 'context'])

    @classmethod
    def __setup__(cls):
        super(Rule, cls).__setup__()
        cls._error_messages.update({
                'invalid_code': 'Your code has errors!',
                'bad_rule_computation': 'An error occured in rule %s.'
                'For more information, activate debug mode and see the logs',
        })

    @classmethod
    def write(cls, rules, values):
        if 'debug_mode' in values and not values['debug_mode']:
            RuleExecutionLog = Pool().get('rule_engine.execution_log')
            RuleExecutionLog.delete(RuleExecutionLog.search([
                ('rule', 'in', [x.id for x in rules])]))
        super(Rule, cls).write(rules, values)

    @classmethod
    def _export_keys(cls):
        return set(['name'])

    @classmethod
    def _export_skips(cls):
        result = super(Rule, cls)._export_skips()
        result.add('debug_mode')
        result.add('exec_logs')
        return result

    def on_change_rule_parameters(self):
        return {'data_tree': self.get_data_tree(None)
            if self.context else '[]'}

    def filter_errors(self, error):
        if isinstance(error, WARNINGS):
            return False
        elif (isinstance(error, pyflakes.messages.UndefinedName)
                and error.message_args[0] in self.allowed_functions):
            return False
        else:
            return True

    def check_code(self):
        result = not bool(filter(
            lambda m: self.filter_errors(m),
            check_code(self.as_function)))
        if result:
            return True
        self.raise_user_error('invalid_code')

    @classmethod
    def validate(cls, rules):
        for rule in rules:
            rule.check_code()
        return True

    @staticmethod
    def default_status():
        return 'draft'

    def get_context_for_execution(self):
        return self.context.get_context(self)

    def add_rule_parameters_to_context(self, evaluation_context, kwargs,
            context):
        if not kwargs:
            kwargs = {}
        for elem in self.rule_parameters:
            elem.as_context(evaluation_context, context, kwargs[elem.code]
                if elem.code in kwargs else None)

    def prepare_context(self, evaluation_context, debug_mode, **kwargs):
        context = self.get_context_for_execution()
        the_result = RuleEngineResult()
        context['__result__'] = the_result
        self.add_rule_parameters_to_context(evaluation_context, kwargs,
            context)
        context.update(evaluation_context)
        context['context'] = context
        return context

    def compute(self, evaluation_context, debug_mode=False, **kwargs):
        with Transaction().set_context(debug=debug_mode):
            context = self.prepare_context(evaluation_context, debug_mode,
                **kwargs)
            the_result = context['__result__']
            localcontext = {}
            try:
                exec self.as_function in context, localcontext
                the_result.result = localcontext[
                    ('result_%s' % hash(self.name)).replace('-', '_')]
                the_result.result_set = True
            except (TooFewFunctionCall, TooManyFunctionCall):
                if debug_mode:
                    raise
            except CatchedRuleEngineError:
                pass
                the_result.result = None
            except UserError:
                raise
            except Exception, exc:
                if self.debug_mode:
                    with Transaction().new_cursor() as transaction:
                        RuleExecution = Pool().get('rule_engine.execution_log')
                        rule_execution = RuleExecution()
                        rule_execution.rule = self
                        rule_execution.create_date = datetime.datetime.now()
                        rule_execution.user = Transaction().user
                        rule_execution.init_from_rule_result(the_result)
                        exc_type, exc_value, exc_traceback = sys.exc_info()
                        tmp = traceback.extract_tb(exc_traceback)
                        last_frame = tmp[-1]
                        if last_frame[2].startswith('fct__'):
                            lineno = last_frame[1] - 3
                            rule_execution.low_level_debug += '\n\n'
                            rule_execution.low_level_debug += 'Error detected '
                            'in rule definition line %d:\n' % lineno
                            rule_execution.low_level_debug += '\n'
                            for line_number, line in enumerate(
                                    self.code.split('\n'), 1):
                                if (line_number >= lineno - 2 and
                                        line_number <= line_number + 2):
                                    if line_number == lineno:
                                        rule_execution.low_level_debug += \
                                            '>>\t' + line + '\n'
                                    else:
                                        rule_execution.low_level_debug += \
                                            '  \t' + line + '\n'
                            rule_execution.low_level_debug += '\n'
                            rule_execution.low_level_debug += str(exc)
                        rule_execution.errors += '\n' + (
                            coop_string.remove_invalid_char(self.name) +
                            ' - ' + str(exc))
                        rule_execution.save()
                        transaction.cursor.commit()
                self.raise_user_error('bad_rule_computation', (self.name))
        return the_result

    def on_change_context(self):
        return {'data_tree': self.get_data_tree(None)
            if self.context else '[]'}

    @property
    def as_function(self):
        code = '\n'.join(' ' + l for l in self.code.splitlines())
        name = ('%s' % hash(self.name)).replace('-', '_')
        code_template = CODE_TEMPLATE % (name, name, name)
        return decistmt(code_template % code)

    def get_data_tree(self, name):
        tmp_result = [e.as_tree() for e in self.context.allowed_elements]
        if not (hasattr(self, 'rule_parameters') and self.rule_parameters):
            return json.dumps(tmp_result)
        tmp_node = {}
        tmp_node['name'] = 'x-y-z'
        tmp_node['translated'] = 'x-y-z'
        tmp_node['fct_args'] = ''
        tmp_node['description'] = 'X-Y-Z'
        tmp_node['type'] = 'folder'
        tmp_node['long_description'] = ''
        tmp_node['children'] = []
        for elem in self.rule_parameters:
            param_node = {}
            param_node['name'] = elem.name
            param_node['translated'] = elem.get_translated_technical_name()
            param_node['fct_args'] = elem.get_fct_args()
            param_node['description'] = elem.get_description()
            param_node['type'] = 'function'
            param_node['long_description'] = elem.get_long_description()
            param_node['children'] = []
            tmp_node['children'].append(param_node)
        tmp_result.append(tmp_node)
        return json.dumps(tmp_result)

    @property
    def allowed_functions(self):
        result = sum([e.as_functions_list()
                for e in self.context.allowed_elements], [])
        result += [elem.get_translated_technical_name()
            for elem in self.rule_parameters]
        return result

    def get_rec_name(self, name=None):
        return self.name


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
        cls._error_messages.update({
                'duplicate_name': ('You have defined twice the same name %s '
                    'in %s and %s'),
        })

    @classmethod
    def validate(cls, contexts):
        super(Context, cls).validate(contexts)
        cls.check_duplicate_name(contexts)

    @classmethod
    def check_duplicate_name(cls, contexts):
        for context in contexts:
            names = {}
            elements = list(context.allowed_elements)
            while elements:
                element = elements.pop()
                if element.translated_technical_name in names:
                    if element != names[element.translated_technical_name]:
                        cls.raise_user_error('duplicate_name', (
                            element.translated_technical_name,
                            element.full_path,
                            names[element.translated_technical_name].full_path,
                            ))
                else:
                    names[element.translated_technical_name] = element
                elements.extend(element.children)

    def get_context(self, rule):
        context = {}
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
    full_path = fields.Function(
        fields.Char('Full Path'), 'get_full_path')

    @classmethod
    def __setup__(cls):
        super(TreeElement, cls).__setup__()
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
        result = coop_string.is_ascii(self.fct_args)
        if result:
            return True
        self.raise_user_error('argument_accent_error')

    def check_name_accents(self):
        if not self.name:
            return True
        result = coop_string.is_ascii(self.translated_technical_name)
        if result:
            return True
        self.raise_user_error('name_accent_error')

    @classmethod
    def validate(cls, records):
        for elem in records:
            elem.check_arguments_accents()
            elem.check_name_accents()
        return True

    @staticmethod
    def default_type():
        return 'function'

    def on_change_description(self):
        if self.translated_technical_name:
            return {}
        return {
            'translated_technical_name':
            coop_string.remove_blank_and_invalid_char(self.description)
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
        def debug_wrapper(func):
            def wrapper_func(*args, **kwargs):
                context['__result__'].low_level_debug.append(
                    'Entering %s (args = %s)' % (
                        self.translated_technical_name, str(args)))
                try:
                    result = func(*args, **kwargs)
                except Exception, exc:
                    context['__result__'].errors.append(
                        'Error in %s : %s' % (
                            self.translated_technical_name, str(exc)))
                    raise
                context['__result__'].low_level_debug.append(
                    'Exiting %s (result = %s)' % (
                        self.translated_technical_name, str(result)))
                return result
            return wrapper_func

        pool = Pool()
        if self.type == 'function':
            namespace_obj = pool.get(self.namespace)
            context[self.translated_technical_name] = debug_wrapper(
                functools.partial(getattr(namespace_obj, self.name), context))
        elif self.type == 'rule':
            context[self.translated_technical_name] = debug_wrapper(
                functools.partial(self.rule.compute, context))
        elif self.type == 'table':
            context[self.translated_technical_name] = debug_wrapper(
                functools.partial(TableCell.get, self.the_table))
        for element in self.children:
            element.as_context(context)
        return context

    def on_change_with_translated_technical_name(self):
        if self.rule:
            return coop_string.remove_blank_and_invalid_char(self.rule.name)

    @staticmethod
    def default_long_description():
        return ''

    def get_full_path(self, name):
        res = ''
        if self.parent:
            res = '%s.' % self.parent.full_path
        res += (self.translated_technical_name
            if self.translated_technical_name else '')
        return res


class ContextTreeElement(ModelSQL):
    "Context Tree Element"
    __name__ = 'rule_engine.context-rule_engine.tree_element'

    context = fields.Many2One(
        'rule_engine.context', 'Context', required=True, ondelete='CASCADE')
    tree_element = fields.Many2One(
        'rule_engine.tree_element', 'Tree Element',
        required=True, ondelete='CASCADE')


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
        fields.Many2One('rule_engine', 'Rule'),
        'get_rule')

    @classmethod
    def __setup__(cls):
        super(TestCaseValue, cls).__setup__()
        cls.__rpc__.update({
            'get_selection': RPC(instantiate=0),
        })

    @classmethod
    def _export_keys(cls):
        return set([])

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


class TestCase(ModelView, ModelSQL):
    "Test Case"
    __name__ = 'rule_engine.test_case'
    _rec_name = 'description'

    description = fields.Char('Description', required=True)
    rule = fields.Many2One(
        'rule_engine', 'Rule', required=True, ondelete='CASCADE')
    expected_result = fields.Char('Expected Result')
    test_values = fields.One2Many(
        'rule_engine.test_case.value', 'test_case', 'Values',
        on_change=['test_values', 'rule'], depends=['rule'],
        context={'rule_id': Eval('rule')})
    result_value = fields.Char('Result Value')
    result_warnings = fields.Text('Result Warnings')
    result_errors = fields.Text('Result Errors')
    result_info = fields.Text('Result Info')
    debug = fields.Text('Debug Info')
    low_debug = fields.Text('Low Level Debug Info')
    rule_text = fields.Function(
        fields.Text('Rule Text', states={'readonly': True}),
        'get_rule_text')

    def get_rule_text(self, name):
        return self.rule.code

    def execute_test(self):
        test_context = {}
        for value in self.test_values:
            if not value.value:
                return {}
            val = safe_eval(value.value if value.value != '' else "''")
            test_context.setdefault(value.name, []).append(val)
        test_context = {
            key: noargs_func(key, value)
            for key, value in test_context.items()}
        return self.rule.compute(test_context, debug_mode=True)

    def on_change_test_values(self):
        try:
            test_result = self.execute_test()
        except Exception as exc:
            result_value = 'ERROR: {}'.format(exc)
            return {
                'result_value': result_value,
                'result_info': '',
                'result_warnings': '',
                'result_errors': '',
                'debug': '',
                'low_debug': '',
                'expected_result': result_value,
            }
        # if test_result.has_errors:
            # test_result.result = 'ERROR'
        return {
            'result_value': test_result.print_result(),
            'result_info': '\n'.join(test_result.print_info()),
            'result_warning': '\n'.join(test_result.print_warnings()),
            'result_errors': '\n'.join(test_result.print_errors()),
            'debug': '\n'.join(test_result.print_debug()),
            'low_debug': '\n'.join(test_result.low_level_debug),
            'expected_result': str(test_result),
        }

    def do_test(self):
        try:
            test_result = self.execute_test()
        except:
            raise
            return False, sys.exc_info()
        try:
            assert str(test_result) == self.expected_result
            return True, None
        except AssertionError:
            return False, str(test_result) + ' vs. ' + str(
                self.expected_result)
        except:
            return False, str(sys.exc_info())

    @classmethod
    def default_rule(cls):
        rule_id = Transaction().context.get('rule_id', None)
        if not rule_id:
            cls.raise_user_error('undefined_rule')
        return rule_id


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


class TableDefinition():
    'Table Definition'

    __metaclass__ = PoolMeta

    __name__ = 'table.table_def'

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


class RuleError(model.CoopSQL, model.CoopView):
    'Rule Error'

    __name__ = 'rule_engine.error'

    code = fields.Char('Code', required=True, on_change_with=['code', 'name'])
    name = fields.Char('Name', required=True, translate=True)
    kind = fields.Selection(
        [('info', 'Info'), ('warning', 'Warning'), ('error', 'Error')], 'Kind',
        required=True)
    arguments = fields.Char('Arguments')

    def __str__(self):
        return '[%s] %s' % (self.kind, self.name)

    @classmethod
    def __setup__(cls):
        super(RuleError, cls).__setup__()
        cls._sql_constraints += [
            ('code_uniq', 'UNIQUE(code)', 'The code must be unique!'),
        ]
        cls._error_messages.update({
            'arg_number_error':
            'Number of arguments does not match string content',
        })

    def check_arguments(self):
        try:
            if self.arguments:
                self.name % tuple(self.arguments.split(','))
            else:
                self.name % ()
        except TypeError:
            self.raise_user_error('arg_number_error')

    @classmethod
    def validate(cls, errors):
        super(RuleError, cls).validate(errors)
        for error in errors:
            error.check_arguments()

    def on_change_with_code(self):
        if self.code:
            return self.code
        elif self.name:
            return coop_string.remove_blank_and_invalid_char(self.name)

    @classmethod
    def get_functional_errors_from_errors(cls, errors):
        domain = [[('code', '=', code)] for code in set(errors)]
        domain.insert(0, 'OR')
        err_dict = dict([x.code, x] for x in cls.search(domain))
        func_err = []
        other = []
        for error in errors:
            if error in err_dict:
                func_err.append(err_dict[error])
            else:
                other.append(error)
        return func_err, other

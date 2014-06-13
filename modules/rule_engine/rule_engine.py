# encoding: utf-8
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
from trytond import backend
from trytond.model import ModelView as TrytonModelView
from trytond.wizard import Wizard, StateView, Button
from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.tools.misc import _compile_source, memoize
from trytond.pyson import Eval, Or

from trytond.modules.cog_utils import fields
from trytond.modules.cog_utils.model import CoopSQL as ModelSQL
from trytond.modules.cog_utils.model import CoopView as ModelView
from trytond.modules.cog_utils import model, utils, coop_string
from trytond.modules.cog_utils import coop_date

from trytond.modules.table import table
from trytond.model import DictSchemaMixin

__all__ = [
    'RuleEngine',
    'RuleEngineTable',
    'RuleEngineRuleEngine',
    'RuleParameter',
    'RuleExecutionLog',
    'Context',
    'RuleFunction',
    'ContextRuleFunction',
    'TestCase',
    'TestCaseValue',
    'RunTests',
    'RunTestsReport',
    'RuleTools',
    'InternalRuleEngineError',
    'CatchedRuleEngineError',
    'check_args',
    'RuleError',
    'RuleEngineResult',
    'RuleEngineTagRelation',
    ]

CODE_TEMPLATE = """
def fct_%s():
 from decimal import Decimal
%%s

result_%s = fct_%s()
"""


def check_code(algorithm):
    try:
        tree = compile(algorithm, 'test', 'exec', _ast.PyCF_ONLY_AST)
    except SyntaxError, syn_error:
        error = pyflakes.messages.Message('test', syn_error)
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


@memoize(1000)
def _compile_source_exec(source):
    return compile(source, '', 'exec')


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
                'datetime': datetime,
                'int': int,
                'max': max,
                'min': min,
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

    def __init__(self, result=None):
        super(RuleEngineResult, self).__init__()
        self.errors = []
        self.warnings = []
        self.info = []
        self.debug = []
        self.low_level_debug = []
        self.result = result
        self.result_set = False

    @property
    def has_errors(self):
        return bool(self.errors)

    def __str__(self):
        return unicode(self).encode('utf-8')

    def __unicode__(self):
        result = '[' + self.print_result()
        result += ', [' + ', '.join(self.print_errors()) + ']'
        result += ', [' + ', '.join(self.print_warnings()) + ']'
        result += ', [' + ', '.join(self.print_info()) + ']'
        result += ']'
        return result

    def print_errors(self):
        return map(unicode, self.errors)

    def print_warnings(self):
        return map(unicode, self.warnings)

    def print_info(self):
        return map(unicode, self.info)

    def print_debug(self):
        return map(unicode, self.debug)

    def print_result(self):
        return unicode(self.result)

    def print_low_level_debug(self):
        return map(unicode, self.low_level_debug)


class RuleExecutionLog(ModelSQL, ModelView):
    'Rule Execution Log'

    __name__ = 'rule_engine.log'

    user = fields.Many2One('res.user', 'User', ondelete='SET NULL')
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


class RuleTools(ModelView):
    '''
        Tools functions
    '''
    __name__ = 'rule_engine.runtime'

    @classmethod
    def get_result(cls, args):
        if '__result__' in args:
            return args['__result__']
        raise InternalRuleEngineError('Result not found')

    @classmethod
    def append_error(cls, args, error_msg):
        cls.get_result(args).errors.append(error_msg)

    @classmethod
    def debug(cls, args, debug):
        args['__result__'].debug.append(debug)

    @classmethod
    def _re_years_between(cls, args, date1, date2):
        if (not isinstance(date1, datetime.date)
                or not isinstance(date2, datetime.date)):
            args['errors'].append('years_between needs datetime types')
            raise CatchedRuleEngineError
        return coop_date.number_of_years_between(date1, date2)

    @classmethod
    def _re_days_between(cls, args, date1, date2):
        if (not isinstance(date1, datetime.date)
                or not isinstance(date2, datetime.date)):
            args['errors'].append('days_between needs datetime types')
            raise CatchedRuleEngineError
        return coop_date.number_of_days_between(date1, date2)

    @classmethod
    def _re_today(cls, args):
        return utils.today()

    @classmethod
    def _re_convert_frequency(cls, args, from_frequency, to_frequency):
        return coop_date.convert_frequency(from_frequency, to_frequency)

    @classmethod
    def add_error(cls, args, error_code, custom=False, lvl=None):
        RuleError = Pool().get('functional_error')
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
                if node.func.id not in ('int', 'round', 'max', 'min'):
                    raise LookupError(node.func.id)
            self.functions.append(node.func.id)
        return super(FunctionFinder, self).visit(node)


class RuleEngineTable(model.CoopSQL):
    'Rule_Engine - Table'

    __name__ = 'rule_engine-table'

    parent_rule = fields.Many2One('rule_engine', 'Parent Rule', required=True,
        ondelete='CASCADE')
    table = fields.Many2One('table', 'Table', ondelete='RESTRICT')

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().cursor

        super(RuleEngineTable, cls).__register__(module_name)

         # Migration from 1.1: split rule parameters in multiple table
        table_definition = cls.__table__()
        if TableHandler.table_exist(cursor, 'rule_engine_parameter'):
            cursor.execute(*table_definition.delete())
            cursor.execute("SELECT the_table, parent_rule "
                "FROM rule_engine_parameter "
                "WHERE kind = 'table'")
            for cur_rule_parameter in cursor.dictfetchall():
                cursor.execute(*table_definition.insert(
                    columns=[table_definition.parent_rule,
                    table_definition.table],
                    values=[[cur_rule_parameter['parent_rule'],
                    cur_rule_parameter['the_table']]]))


class RuleEngineRuleEngine(model.CoopSQL):
    'Rule Engine - Rule Engine'

    __name__ = 'rule_engine-rule_engine'

    parent_rule = fields.Many2One('rule_engine', 'Parent Rule', required=True,
        ondelete='CASCADE')
    rule = fields.Many2One('rule_engine', 'Rule', ondelete='RESTRICT')

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().cursor

        super(RuleEngineRuleEngine, cls).__register__(module_name)

         # Migration from 1.1: split rule parameters in multiple table
        rule_definition = cls.__table__()
        if TableHandler.table_exist(cursor, 'rule_engine_parameter'):
            cursor.execute(*rule_definition.delete())
            cursor.execute("SELECT the_rule, parent_rule "
                "FROM rule_engine_parameter "
                "WHERE kind = 'rule'")
            for cur_rule_parameter in cursor.dictfetchall():
                cursor.execute(*rule_definition.insert(
                    columns=[rule_definition.parent_rule,
                    rule_definition.rule],
                    values=[[cur_rule_parameter['parent_rule'],
                    cur_rule_parameter['the_rule']]]))


class RuleParameter(DictSchemaMixin, model.CoopSQL, model.CoopView):
    'Rule Parameter'

    __name__ = 'rule_engine.rule_parameter'

    parent_rule = fields.Many2One('rule_engine', 'Parent Rule', required=True,
        ondelete='CASCADE')

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().cursor

        super(RuleParameter, cls).__register__(module_name)

         # Migration from 1.1: split rule parameters in multiple table
        parameter_definition = cls.__table__()
        if TableHandler.table_exist(cursor, 'rule_engine_parameter'):
            cursor.execute(*parameter_definition.delete())
            cursor.execute("SELECT name, code, parent_rule "
                "FROM rule_engine_parameter "
                "WHERE kind = 'kwarg'")
            for cur_rule_parameter in cursor.dictfetchall():
                cursor.execute(*parameter_definition.insert(
                    columns=[parameter_definition.parent_rule,
                    parameter_definition.name, parameter_definition.string,
                    parameter_definition.type_],
                    values=[[cur_rule_parameter['parent_rule'],
                    cur_rule_parameter['code'], cur_rule_parameter['name'],
                    'numeric']]))
            cursor.execute("SELECT name, code, parent_rule "
                "FROM rule_engine_parameter "
                "WHERE kind = 'rule_compl'")
            for cur_rule_parameter in cursor.dictfetchall():
                cursor.execute(*parameter_definition.insert(
                    columns=[parameter_definition.parent_rule,
                    parameter_definition.name, parameter_definition.string,
                    parameter_definition.type_],
                    values=[[cur_rule_parameter['parent_rule'],
                    cur_rule_parameter['code'], cur_rule_parameter['name'],
                    'numeric']]))

    @fields.depends('string', 'name')
    def on_change_with_name(self):
        if self.name:
            return self.name
        return coop_string.remove_blank_and_invalid_char(self.string)

    @classmethod
    def __setup__(cls):
        super(RuleParameter, cls).__setup__()
        cls.name.string = 'Code'
        cls.string.string = 'Name'


class RuleEngine(ModelView, ModelSQL):
    "Rule"
    __name__ = 'rule_engine'

    name = fields.Char('Name', required=True)
    context = fields.Many2One('rule_engine.context', 'Context',
        ondelete='RESTRICT')
    short_name = fields.Char('Code', required=True)
        #TODO : rename as code (before code was the name for algorithm)
    algorithm = fields.Text('Algorithm')
    data_tree = fields.Function(fields.Text('Data Tree'),
        'on_change_with_data_tree')
    test_cases = fields.One2Many('rule_engine.test_case', 'rule', 'Test Cases',
        states={'invisible': Eval('id', 0) <= 0},
        context={'rule_id': Eval('id')})
    status = fields.Selection([
            ('draft', 'Draft'),
            ('validated', 'Validated')],
        'Status')
    debug_mode = fields.Boolean('Debug Mode')
    exec_logs = fields.One2Many('rule_engine.log', 'rule', 'Execution Logs',
        states={'readonly': True, 'invisible': ~Eval('debug_mode')},
        depends=['debug_mode'], order=[('create_date', 'DESC')])
    parameters = fields.One2Many('rule_engine.rule_parameter', 'parent_rule',
        'Parameters', states={'invisible': Or(
                Eval('extra_data_kind') != 'parameter',
                ~Eval('extra_data'),
                )
            }, depends=['extra_data_kind', 'extra_data'])
    rules_used = fields.Many2Many(
        'rule_engine-rule_engine', 'parent_rule', 'rule', 'Rules',
        states={'invisible': Or(
                Eval('extra_data_kind') != 'rule',
                ~Eval('extra_data'),
                )
            }, depends=['extra_data_kind', 'extra_data'])
    tables_used = fields.Many2Many(
        'rule_engine-table', 'parent_rule', 'table', 'Tables',
        states={'invisible': Or(
                Eval('extra_data_kind') != 'table',
                ~Eval('extra_data'),
                )
            }, depends=['extra_data_kind', 'extra_data'])
    extra_data = fields.Function(fields.Boolean('Display Extra Data'),
        'get_extra_data', 'setter_void')
    extra_data_kind = fields.Function(
        fields.Selection([
                ('', ''),
                ('parameter', 'Parameter'),
                ('rule', 'Rule'),
                ('table', 'Table')],
            'Kind', states={'invisible': ~Eval('extra_data')}),
        'get_extra_data_kind', 'setter_void')
    tags = fields.Many2Many('rule_engine-tag', 'rule_engine', 'tag', 'Tags')
    tags_name = fields.Function(
        fields.Char('Tags'),
        'on_change_with_tags_name', searcher='search_tags')

    @classmethod
    def __setup__(cls):
        super(RuleEngine, cls).__setup__()
        cls._error_messages.update({
                'invalid_code': 'Your algorithm has errors!',
                'bad_rule_computation': 'An error occured in rule %s.'
                'For more information, activate debug mode and see the logs'
                '\n\nError info :\n%s',
                'execute_draft_rule': 'The rule %s is a draft.'
                'Update the rule status to "Validated"',
                'kwarg_expected': 'Expected %s as a parameter for rule %s',
                })
        cls._sql_constraints += [
            ('code_unique', 'UNIQUE(short_name)',
                'The code must be unique'),
            ]

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().cursor

        super(RuleEngine, cls).__register__(module_name)

        the_table = TableHandler(cursor, cls, module_name)
        rule = cls.__table__()
        # Migration from 1.1: move code to algorithm - add short_name
        if the_table.column_exist('code'):
            the_table.drop_constraint('name_unique')
            cursor.execute(*rule.update(
                    [rule.algorithm],
                    [rule.code]))
            cursor.execute("UPDATE rule_engine "
                "SET algorithm = REPLACE(algorithm, 'rule_compl_', 'param_')")
            cursor.execute("UPDATE rule_engine "
                "SET algorithm = REPLACE(algorithm, 'kwarg_', 'param_')")
            the_table.drop_column('code')
            cursor.execute(*rule.update(
                    [rule.short_name],
                    [rule.name]))
            cursor.execute("UPDATE rule_engine "
                "SET short_name = TRANSLATE(short_name,"
                "'éèêàù-%+:. ', 'eeeau______')")

    @classmethod
    def write(cls, rules, values):
        if 'debug_mode' in values and not values['debug_mode']:
            RuleExecutionLog = Pool().get('rule_engine.log')
            RuleExecutionLog.delete(RuleExecutionLog.search([
                ('rule', 'in', [x.id for x in rules])]))
        super(RuleEngine, cls).write(rules, values)

    @classmethod
    def _export_keys(cls):
        return set(['short_name'])

    @classmethod
    def _export_skips(cls):
        result = super(RuleEngine, cls)._export_skips()
        result.add('debug_mode')
        result.add('exec_logs')
        return result

    @classmethod
    def fill_empty_data_tree(cls):
        res = []
        for label_type in ('parameters', 'rules_used', 'tables_used'):
            tmp_node = {}
            tmp_node['name'] = ''
            tmp_node['translated'] = ''
            tmp_node['fct_args'] = ''
            tmp_node['description'] = coop_string.translate_label(cls,
                label_type)
            tmp_node['type'] = 'folder'
            tmp_node['long_description'] = ''
            tmp_node['children'] = []
            res.append(tmp_node)
        return res

    @classmethod
    def default_data_tree(cls):
        data_tree = cls.fill_empty_data_tree()
        return json.dumps(data_tree)

    @fields.depends('rules_used', 'tables_used',
        'parameters', 'context')
    def on_change_with_data_tree(self, name=None):
        return json.dumps(self.data_tree_structure())

    @fields.depends('short_name', 'name')
    def on_change_with_short_name(self):
        if self.short_name:
            return self.short_name
        return coop_string.remove_blank_and_invalid_char(self.name)

    @classmethod
    def _post_import(cls, rules):
        cls.validate(rules)

    @classmethod
    def validate(cls, rules):
        super(RuleEngine, cls).validate(rules)
        for rule in rules:
            if rule.status == 'validated':
                rule.check_code()

    @staticmethod
    def default_status():
        return 'draft'

    def filter_errors(self, error):
        if isinstance(error, WARNINGS):
            return False
        elif (isinstance(error, pyflakes.messages.UndefinedName)
                and error.message_args[0] in self.allowed_functions()):
            return False
        else:
            return True

    def check_code(self):
        if '__importing__' in Transaction().context:
            return True
        result = not bool(filter(
            lambda m: self.filter_errors(m),
            check_code(self.as_function)))
        if result:
            return True
        self.raise_user_error('invalid_code')

    def get_extra_data_for_on_change(self, existing_values):
        if not getattr(self, 'parameters', None):
            return None
        return dict([(elem.name, existing_values.get(
                        elem.name, None))
                for elem in self.parameters])

    def get_context_for_execution(self):
        return self.context.get_context(self)

    def execute_rule(self, the_rule, evaluation_context, **execution_kwargs):
        result = the_rule.execute(evaluation_context, execution_kwargs)
        if result.has_errors:
            raise InternalRuleEngineError(
                'Impossible to evaluate parameter %s when computing rule %s' %
                (the_rule.short_name, self.name))
        return result.result

    def as_context(self, elem, kind, evaluation_context, context, forced_value,
            debug=False):
        if not forced_value:
            if kind == 'param':
                self.raise_user_error('kwarg_expected', (elem.name,
                        self.name))
        technical_name = self.get_translated_name(elem, kind)
        if forced_value:
            context[technical_name] = lambda: forced_value
        elif kind == 'rule':
            context[technical_name] = \
                functools.partial(self.execute_rule, elem, evaluation_context)
        elif kind == 'table':
            context[technical_name] = \
                functools.partial(table.TableCell.get, elem)
        else:
            return
        if debug:
            debug_wrapper = self.get_wrapper_func(context)
            context[technical_name] = debug_wrapper(context[technical_name])

    def add_rule_parameters_to_context(self, evaluation_context,
            execution_kwargs, context):

        for elem in self.parameters:
            if elem.name in execution_kwargs:
                forced_value = execution_kwargs[elem.name]
            else:
                forced_value = None
            self.as_context(elem, 'param', evaluation_context, context,
                forced_value, Transaction().context.get('debug'))
        for elem in self.tables_used:
            self.as_context(elem, 'table', evaluation_context, context, None,
                Transaction().context.get('debug'))
        for elem in self.rules_used:
            self.as_context(elem, 'rule', evaluation_context, context, None,
                Transaction().context.get('debug'))

    def prepare_context(self, evaluation_context, execution_kwargs):
        context = self.get_context_for_execution()
        the_result = RuleEngineResult()
        context['__result__'] = the_result
        self.add_rule_parameters_to_context(evaluation_context,
            execution_kwargs, context)
        context.update(evaluation_context)
        context['context'] = context
        return context

    def get_wrapper_func(self, context):
        def debug_wrapper(func):
            def wrapper_func(*args, **kwargs):
                context['__result__'].low_level_debug.append(
                    'Entering %s' % self.get_rec_name(None))
                if args:
                    context['__result__'].low_level_debug.append(
                        '\targs : %s' % str(args))
                if kwargs:
                    context['__result__'].low_level_debug.append(
                        '\tkwargs : %s' % str(kwargs))
                try:
                    result = func(*args, **kwargs)
                except Exception, exc:
                    context['__result__'].errors.append(
                        'ERROR in %s : %s' % (
                            self.get_rec_name(None), str(exc)))
                    raise
                context['__result__'].low_level_debug.append(
                    '\tresult = %s' % str(result))
                return result
            return wrapper_func
        return debug_wrapper

    def compute(self, evaluation_context, execution_kwargs):
        with Transaction().set_context(debug=self.debug_mode or
                'force_debug_mode' in Transaction().context):
            context = self.prepare_context(evaluation_context,
                execution_kwargs)
            the_result = context['__result__']
            localcontext = {}
            try:
                comp = _compile_source_exec(self.as_function)
                exec comp in context, localcontext
                if (not Transaction().context.get('debug') and
                        self.status == 'draft'):
                    self.raise_user_error('execute_draft_rule', (self.name))
                the_result.result = localcontext[
                    ('result_%s' % hash(self.name)).replace('-', '_')]
                the_result.result_set = True
            except (TooFewFunctionCall, TooManyFunctionCall):
                if self.debug_mode:
                    raise
            except CatchedRuleEngineError:
                pass
                the_result.result = None
            except Exception, exc:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                tmp = traceback.extract_tb(exc_traceback)
                last_frame = tmp[-1]
                if last_frame[2].startswith('fct_'):
                    lineno = last_frame[1] - 3
                    stack_info = '\n\n'
                    stack_info += 'Error detected '
                    'in rule definition line %d:\n' % lineno
                    stack_info += '\n'
                    for line_number, line in enumerate(
                            self.algorithm.split('\n'), 1):
                        if (line_number >= lineno - 2 and
                                line_number <= lineno + 2):
                            if line_number == lineno:
                                stack_info += \
                                    '>>\t' + line + '\n'
                            else:
                                stack_info += \
                                    '  \t' + line + '\n'
                    stack_info += '\n'
                    stack_info += str(exc)
                    the_result.low_level_debug.append(stack_info)
                if self.debug_mode:
                    with Transaction().new_cursor() as transaction:
                        RuleExecution = Pool().get('rule_engine.log')
                        rule_execution = RuleExecution()
                        rule_execution.rule = self
                        rule_execution.create_date = datetime.datetime.now()
                        rule_execution.user = Transaction().user
                        rule_execution.init_from_rule_result(the_result)
                        rule_execution.errors += '\n' + (
                            coop_string.remove_invalid_char(self.name) +
                            ' - ' + str(exc))
                        rule_execution.save()
                        DatabaseOperationalError = backend.get(
                            'DatabaseOperationalError')
                        try:
                            transaction.cursor.commit()
                        except DatabaseOperationalError:
                            transaction.cursor.rollback()
                if self.debug_mode:
                    the_result.result = str(exc)
                    return the_result
                self.raise_user_error('bad_rule_computation', (self.name,
                        str(exc.args)))
        return the_result

    @property
    def as_function(self):
        code = '\n'.join(' ' + l for l in self.algorithm.splitlines())
        name = ('%s' % hash(self.name)).replace('-', '_')
        code_template = CODE_TEMPLATE % (name, name, name)
        return decistmt(code_template % code)

    def get_translated_name(self, elem, kind):
        if kind == 'table':
            return '%s_%s' % (kind, elem.code)
        elif kind == 'rule':
            return '%s_%s' % (kind, elem.short_name)
        elif kind == 'param':
            return '%s_%s' % (kind, elem.name)

    def get_fct_args(self, elem, kind):
        if kind == 'table':
            dimension_names = []
            for idx in range(1, table.DIMENSION_MAX + 1):
                dim = getattr(elem, 'dimension_kind%s' % idx, None)
                if not dim:
                    break
                dim_name = getattr(elem, 'dimension_name%s' % idx, None)
                if not dim_name:
                    dim_name = 'Col #%s' % idx
                dimension_names.append(dim_name)
            res = ', '.join(
                map(coop_string.remove_invalid_char, dimension_names))
        elif kind == 'rule':
            res = ', '.join(('%s=' % elem.name
                for elem in elem.parameters))
        else:
            res = ''
        return res

    def build_node(self, elem, kind):
        return {
            'name': name,
            'description': elem.get_rec_name(None),
            'type': 'function',
            'long_description': '%s (%s)' % (elem.get_rec_name(None), kind),
            'children': [],
            'translated': self.get_translated_name(elem, kind),
            'fct_args': self.get_fct_args(elem, kind),
            }

    def data_tree_structure_for_kind(self, data_tree, tree_node_name,
            kind_code, elements):
        tmp_node = {}
        tmp_node['name'] = ''
        tmp_node['translated'] = ''
        tmp_node['fct_args'] = ''
        tmp_node['description'] = tree_node_name
        tmp_node['type'] = 'folder'
        tmp_node['long_description'] = ''
        tmp_node['children'] = []
        for elem in elements:
            param_node = self.build_node(elem, kind_code)
            tmp_node['children'].append(param_node)
        data_tree.append(tmp_node)

    def data_tree_structure(self):
        if self.context:
            res = [e.as_tree() for e in self.context.allowed_elements]
        else:
            res = []

        self.data_tree_structure_for_kind(res,
            coop_string.translate_label(self, 'parameters'),
            'param', self.parameters)
        self.data_tree_structure_for_kind(res,
            coop_string.translate_label(self, 'rules_used'), 'rule',
            self.rules_used)
        self.data_tree_structure_for_kind(res,
            coop_string.translate_label(self, 'tables_used'), 'table',
            self.tables_used)
        return res

    def allowed_functions(self):
        result = sum([e.as_functions_list()
                for e in self.context.allowed_elements], [])
        result += [self.get_translated_name(elem, 'table')
            for elem in self.tables_used]
        result += [self.get_translated_name(elem, 'rule')
            for elem in self.rules_used]
        result += [self.get_translated_name(elem, 'param')
            for elem in self.parameters]
        return result

    def get_rec_name(self, name=None):
        return self.name

    def get_extra_data(self, name):
        return False

    def get_extra_data_kind(self, name):
        return ''

    @classmethod
    def default_algorithm(cls):
        return 'return'

    @fields.depends('tags')
    def on_change_with_tags_name(self, name=None):
        return ', '.join([x.name for x in self.tags])

    @classmethod
    def search_tags(cls, name, clause):
        return [('tags.name',) + tuple(clause[1:])]

    def execute(self, arguments, parameters=None):
        result = self.compute(arguments,
            {} if parameters is None else parameters)
        if not self.id or not getattr(self, 'debug_mode', None):
            return result
        DatabaseOperationalError = backend.get('DatabaseOperationalError')
        with Transaction().new_cursor() as transaction:
            RuleExecution = Pool().get('rule_engine.log')
            rule_execution = RuleExecution()
            rule_execution.rule = self.id
            rule_execution.create_date = datetime.datetime.now()
            rule_execution.user = transaction.user
            rule_execution.init_from_rule_result(result)
            rule_execution.save()
            try:
                transaction.cursor.commit()
            except DatabaseOperationalError:
                transaction.cursor.rollback()
        return result


class Context(ModelView, ModelSQL):
    "Context"
    __name__ = 'rule_engine.context'

    name = fields.Char('Name', required=True)
    allowed_elements = fields.Many2Many('rule_engine.context-function',
        'context', 'tree_element', 'Allowed tree elements')

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
            element.as_context(context, Transaction().context.get('debug'))
        return context

    @classmethod
    def _export_light(cls):
        result = super(Context, cls)._export_light()
        result.add('allowed_elements')
        return result


class RuleFunction(ModelView, ModelSQL):
    'Rule Engine Function'
    __name__ = 'rule_engine.function'
    _rec_name = 'description'

    description = fields.Char('Description')
    rule = fields.Many2One('rule_engine', 'Rule', states={
            'invisible': Eval('type') != 'rule',
            'required': Eval('type') == 'rule'},
        depends=['rule'], ondelete='RESTRICT')
    name = fields.Char('Name', states={
            'invisible': ~Eval('type').in_(['function']),
            'required': Eval('type').in_(['function'])},
        depends=['type'])
    namespace = fields.Char('Namespace', states={
            'invisible': Eval('type') != 'function',
            'required': Eval('type') == 'function'},
        depends=['type'])
    type = fields.Selection([
            ('folder', 'Folder'),
            ('function', 'Function')],
        'Type', required=True)
    parent = fields.Many2One('rule_engine.function', 'Parent',
        ondelete='SET NULL')
    children = fields.One2Many('rule_engine.function', 'parent', 'Children')
    translated_technical_name = fields.Char('Translated technical name',
        states={
            'invisible': ~Eval('type').in_(['function', 'rule', 'table']),
            'required': Eval('type').in_(['function', 'rule', 'table'])},
        depends=['type'])
    fct_args = fields.Char('Function Arguments',
        states={'invisible': Eval('type') != 'function'})
    language = fields.Many2One('ir.lang', 'Language', required=True,
        ondelete='RESTRICT',)
    long_description = fields.Text('Long Description')
    full_path = fields.Function(
        fields.Char('Full Path'),
        'get_full_path')

    @classmethod
    def __setup__(cls):
        super(RuleFunction, cls).__setup__()
        cls._error_messages.update({
                'argument_accent_error':
                'Function arguments must only use ascii',
                'name_accent_error': 'Technical name must only use ascii',
                })

    @classmethod
    def _export_keys(cls):
        return set(['type', 'translated_technical_name', 'language.code'])

    @classmethod
    def _export_force_recreate(cls):
        result = super(RuleFunction, cls)._export_force_recreate()
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
        super(RuleFunction, cls).validate(records)
        for elem in records:
            elem.check_arguments_accents()
            elem.check_name_accents()

    @staticmethod
    def default_type():
        return 'function'

    @fields.depends('description', 'translated_technical_name')
    def on_change_description(self):
        if self.translated_technical_name:
            return {}
        return {
            'translated_technical_name':
            coop_string.remove_blank_and_invalid_char(self.description)
            }

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
        if self.type == 'function':
            return [self.translated_technical_name]
        else:
            return sum([
                child.as_functions_list() for child in self.children], [])

    def as_context(self, context, debug=False):
        def debug_wrapper(func):
            def wrapper_func(*args, **kwargs):
                context['__result__'].low_level_debug.append(
                    'Entering %s' % self.translated_technical_name)
                if args:
                    context['__result__'].low_level_debug.append(
                        '\targs : %s' % str(args))
                if kwargs:
                    context['__result__'].low_level_debug.append(
                        '\tkwargs : %s' % str(kwargs))
                try:
                    result = func(*args, **kwargs)
                except Exception, exc:
                    context['__result__'].errors.append(
                        'ERROR in %s : %s' % (
                            self.translated_technical_name, str(exc)))
                    raise
                context['__result__'].low_level_debug.append(
                    '\tresult = %s' % str(result))
                return result
            return wrapper_func

        pool = Pool()
        if self.type == 'function':
            namespace_obj = pool.get(self.namespace)
            context[self.translated_technical_name] = \
                functools.partial(getattr(namespace_obj, self.name), context)
            if debug:
                context[self.translated_technical_name] = debug_wrapper(
                    context[self.translated_technical_name])
        for element in self.children:
            element.as_context(context, debug)
        return context

    @fields.depends('rule')
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


class ContextRuleFunction(ModelSQL):
    'Context Rule Function'
    __name__ = 'rule_engine.context-function'

    context = fields.Many2One('rule_engine.context', 'Context', required=True,
        ondelete='CASCADE')
    tree_element = fields.Many2One('rule_engine.function', 'Rule Function',
        required=True, ondelete='CASCADE')


class TestCaseValue(ModelView, ModelSQL):
    'Test Case Value'
    __name__ = 'rule_engine.test_case.value'

    name = fields.Selection('get_selection', 'Name',
        depends=['rule', 'test_case'])
    value = fields.Char('Value', states={'invisible': ~Eval('override_value')})
    override_value = fields.Boolean('Override Value')
    test_case = fields.Many2One('rule_engine.test_case', 'Test Case',
        ondelete='CASCADE', required=True)
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

    @fields.depends('rule', 'test_case')
    def get_selection(self):
        if (hasattr(self, 'rule') and self.rule):
            rule = self.rule
        elif 'rule_id' in Transaction().context:
            rule = Pool().get('rule_engine')(
                Transaction().context.get('rule_id'))
        else:
            return [('', '')]
        rule_name = ('fct_%s' % hash(rule.name)).replace('-', '_')
        func_finder = FunctionFinder(
            ['Decimal', rule_name] + rule.allowed_functions())
        ast_node = ast.parse(rule.as_function)
        func_finder.visit(ast_node)
        test_values = list(set([
            (n, n) for n in func_finder.functions
            if n not in (rule_name, 'Decimal')]))
        return test_values + [('', '')]

    @classmethod
    def default_override_value(cls):
        return True

    @classmethod
    def _validate(cls, records, field_names=None):
        if Transaction().context.get('__importing__'):
            return
        super(TestCaseValue, cls)._validate(records, field_names)

    @classmethod
    def _post_import(cls, test_case_values):
        cls._validate(test_case_values)


class TestCase(ModelView, ModelSQL):
    'Test Case'
    __name__ = 'rule_engine.test_case'
    _rec_name = 'description'

    description = fields.Char('Description', required=True)
    rule = fields.Many2One('rule_engine', 'Rule', required=True,
        ondelete='CASCADE')
    expected_result = fields.Char('Expected Result')
    test_values = fields.One2Many('rule_engine.test_case.value', 'test_case',
        'Values', depends=['rule'],
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

    @classmethod
    def __setup__(cls):
        super(TestCase, cls).__setup__()
        cls._buttons.update({'recalculate': {}})

    @classmethod
    def default_rule_text(cls):
        if 'rule_id' not in Transaction().context:
            return ''
        Rule = Pool().get('rule_engine')
        return Rule(Transaction().context.get('rule_id')).algorithm

    def get_rule_text(self, name):
        return self.rule.algorithm

    def execute_test(self):
        test_context = {}
        for value in self.test_values:
            if not value.override_value:
                continue
            val = safe_eval(value.value if value.value != '' else "''")
            test_context.setdefault(value.name, []).append(val)
        test_context = {
            key: noargs_func(key, value)
            for key, value in test_context.items()}
        with Transaction().set_context(force_debug_mode=True):
            return self.rule.execute(test_context)

    @fields.depends('test_values', 'rule')
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
        if test_result == {}:
            return {}
        return {
            'result_value': test_result.print_result(),
            'result_info': '\n'.join(test_result.print_info()),
            'result_warning': '\n'.join(test_result.print_warnings()),
            'result_errors': '\n'.join(test_result.print_errors()),
            'debug': '\n'.join(test_result.print_debug()),
            'low_debug': '\n'.join(test_result.print_low_level_debug()),
            'expected_result': str(test_result),
            }

    @classmethod
    @TrytonModelView.button
    def recalculate(cls, instances):
        for elem in instances:
            result = elem.on_change_test_values()
            for k, v in result.iteritems():
                setattr(elem, k, v)
            elem.save()

    def do_test(self):
        try:
            test_result = self.execute_test()
        except:
            raise
            return False, sys.exc_info()
        try:
            assert unicode(test_result) == self.expected_result
            return True, None
        except AssertionError:
            return False, unicode(test_result) + ' vs. ' + self.expected_result
        except:
            return False, str(sys.exc_info())

    @classmethod
    def default_test_values(cls):
        if 'rule_id' not in Transaction().context:
            return []
        Rule = Pool().get('rule_engine')
        the_rule = Rule(Transaction().context.get('rule_id'))
        errors = check_code(the_rule.as_function)
        result = []
        allowed_functions = the_rule.allowed_functions()
        for error in errors:
            if (isinstance(error, pyflakes.messages.UndefinedName)
                    and error.message_args[0] in allowed_functions):
                element_name = error.message_args[0]
                result.append({
                        'name': element_name,
                        'value': '',
                        'override_value': not element_name.startswith(
                            'table_')})
            elif not isinstance(error, WARNINGS):
                raise Exception('Invalid rule')
        return result


class RunTestsReport(ModelView):
    'Test Run Report'
    __name__ = 'rule_engine.run_tests.results'

    report = fields.Text('Report', readonly=True)


class RunTests(Wizard):
    "Run the test cases"
    __name__ = 'rule_engine.run_tests'
    start_state = 'report'

    report = StateView(
        'rule_engine.run_tests.results',
        'rule_engine.rule_engine_run_tests_results_form', [
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
        return {'report': '\n\n'.join(results)}


class RuleError(model.CoopSQL, model.CoopView):
    'Rule Error'

    __name__ = 'functional_error'

    code = fields.Char('Code', required=True)
    name = fields.Char('Name', required=True, translate=True)
    kind = fields.Selection([
            ('info', 'Info'),
            ('warning', 'Warning'),
            ('error', 'Error')],
        'Kind', required=True)
    arguments = fields.Char('Arguments')

    def __str__(self):
        return unicode(self).encode('utf-8')

    def __unicode__(self):
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

    @fields.depends('code', 'name')
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


class RuleEngineTagRelation(model.CoopSQL):
    'Relation between rule engine and tag'

    __name__ = 'rule_engine-tag'

    rule_engine = fields.Many2One('rule_engine', 'Rule Engine',
        ondelete='CASCADE')
    tag = fields.Many2One('tag', 'Tag', ondelete='RESTRICT')

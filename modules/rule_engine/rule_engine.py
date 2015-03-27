# encoding: utf-8
import sys
import traceback
import ast
import _ast
import tokenize
import functools
import json
import datetime
import pyflakes.messages
import logging

from StringIO import StringIO
from decimal import Decimal
from pyflakes.checker import Checker
from sql.aggregate import Count
from sql.conditionals import Coalesce

from trytond import backend
from trytond.rpc import RPC
from trytond.cache import Cache
from trytond.model import DictSchemaMixin, ModelView as TrytonModelView
from trytond.wizard import Wizard, StateView, Button, StateTransition
from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.tools.misc import _compile_source, memoize
from trytond.pyson import Eval, Or, Bool, Not

from trytond.modules.cog_utils import (coop_date, coop_string, fields,
    model, utils)
from trytond.modules.cog_utils.model import CoopSQL as ModelSQL
from trytond.modules.cog_utils.model import CoopView as ModelView
from trytond.modules.table import table

__all__ = [
    'debug_wrapper',
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
    'InitTestCaseFromExecutionLog',
    'ValidateRuleTestCases',
    'RuleMixin',
    ]

CODE_TEMPLATE = """
def fct_%s():
 from decimal import Decimal
 import datetime
 from dateutil.relativedelta import relativedelta
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
                if arg not in args[1]:
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


def debug_wrapper(base_context, func, name):
    def wrapper_func(*args, **kwargs):
        call = [name, '', '', '']
        base_context['__result__'].low_level_debug.append(
            'Entering %s' % name)
        if args:
            call[1] = str(args)
            base_context['__result__'].low_level_debug.append(
                '\targs : %s' % str(args))
        if kwargs:
            call[2] = str(kwargs)
            base_context['__result__'].low_level_debug.append(
                '\tkwargs : %s' % str(kwargs))
        try:
            result = func(*args, **kwargs)
        except Exception, exc:
            call[3] = str(exc)
            base_context['__result__'].calls.append(call)
            base_context['__result__'].errors.append(
                'ERROR in %s : %s' % (
                    name, str(exc)))
            raise
        call[3] = repr(result)
        base_context['__result__'].calls.append(call)
        base_context['__result__'].low_level_debug.append(
            '\tresult = %s' % str(result))
        return result
    return wrapper_func


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


class RuleMixin(object):
    'Rule Mixin'

    __name__ = 'rule_engine.rule_mixin'

    rule = fields.Many2One('rule_engine', 'Rule Engine', required=True,
        ondelete='RESTRICT')
    rule_extra_data = fields.Dict('rule_engine.rule_parameter',
        'Rule Extra Data', states={
            'invisible': Not(Bool(Eval('rule_extra_data', False)))})
    rule_extra_data_string = rule_extra_data.translated('rule_extra_data')

    def calculate(self, args):
        return self.rule.execute(args, self.rule_extra_data).result

    @fields.depends('rule', 'rule_extra_data')
    def on_change_with_rule_extra_data(self):
        if not self.rule:
            return {}
        return self.rule.get_extra_data_for_on_change(
            self.rule_extra_data)


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
        self.calls = []

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
    rule = fields.Many2One('rule_engine', 'Rule', ondelete='CASCADE',
        select=True, required=True)
    errors = fields.Text('Errors', states={'readonly': True})
    warnings = fields.Text('Warnings', states={'readonly': True})
    info = fields.Text('Info', states={'readonly': True})
    debug = fields.Text('Debug', states={'readonly': True})
    low_level_debug = fields.Text('Execution Trace', states={'readonly': True})
    result = fields.Char('Result', states={'readonly': True})
    calls = fields.Text('Calls', states={'readonly': True})
    calculation_date = fields.Date('Calculation Date', readonly=True)

    @classmethod
    def __setup__(cls):
        super(RuleExecutionLog, cls).__setup__()
        cls._order.insert(0, ('calculation_date', 'DESC'))

    def init_from_rule_result(self, result):
        self.errors = '\n'.join(result.print_errors())
        self.warnings = '\n'.join(result.print_warnings())
        self.info = '\n'.join(result.print_info())
        self.debug = '\n'.join(result.print_debug())
        self.low_level_debug = '\n'.join(result.low_level_debug)
        self.result = result.print_result()
        self.calls = '\n'.join(['|&|'.join(x) for x in result.calls])

    @classmethod
    @ModelView.button_action('rule_engine.act_test_case_init')
    def create_test_case(cls, logs):
        pass


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
        if (not isinstance(date1, datetime.date) or
                not isinstance(date2, datetime.date)):
            args['errors'].append('years_between needs datetime types')
            raise CatchedRuleEngineError
        return coop_date.number_of_years_between(date1, date2)

    @classmethod
    def _re_days_between(cls, args, date1, date2):
        if (not isinstance(date1, datetime.date) or
                not isinstance(date2, datetime.date)):
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
        if (isinstance(node, ast.Call) and
                isinstance(node.func, ast.Name)):
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
        return coop_string.slugify(self.string)

    @classmethod
    def __setup__(cls):
        super(RuleParameter, cls).__setup__()
        cls.name.string = 'Code'
        cls.string.string = 'Name'


class RuleEngine(ModelView, ModelSQL, model.TaggedMixin):
    "Rule"
    __name__ = 'rule_engine'
    _func_key = 'short_name'

    name = fields.Char('Name', required=True, translate=True)
    context = fields.Many2One('rule_engine.context', 'Context',
        ondelete='RESTRICT')
    short_name = fields.Char('Code', required=True)
    # TODO : rename as code (before code was the name for algorithm)
    algorithm = fields.Text('Algorithm')
    data_tree = fields.Function(fields.Text('Data Tree'),
        'on_change_with_data_tree')
    test_cases = fields.One2Many('rule_engine.test_case', 'rule', 'Test Cases',
        states={'invisible': Eval('id', 0) <= 0},
        context={'rule_id': Eval('id')}, delete_missing=True)
    status = fields.Selection([
            ('draft', 'Draft'),
            ('validated', 'Validated')],
        'Status')
    status_string = status.translated('status')
    type_ = fields.Selection([('', '')], 'Type')
    debug_mode = fields.Boolean('Debug Mode')
    exec_logs = fields.One2Many('rule_engine.log', 'rule', 'Execution Logs',
        states={'readonly': True, 'invisible': ~Eval('debug_mode')},
        depends=['debug_mode'], delete_missing=True)
    execution_code = fields.Function(fields.Text('Execution Code'),
        'on_change_with_execution_code')
    parameters = fields.One2Many('rule_engine.rule_parameter', 'parent_rule',
        'Parameters', delete_missing=True, states={'invisible': Or(
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
    extra_data_kind_string = extra_data_kind.translated('extra_data_kind')
    passing_test_cases = fields.Function(
        fields.Boolean('Test Cases OK'),
        'get_passing_test_cases', searcher='search_passing_test_cases')

    _prepare_context_cache = Cache('prepare_context')

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
                'kwarg_expected': 'Expected %s as a parameter',
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
        cls._prepare_context_cache.clear()
        super(RuleEngine, cls).write(rules, values)

    @classmethod
    def is_master_object(cls):
        return True

    @classmethod
    def _export_skips(cls):
        result = super(RuleEngine, cls)._export_skips()
        result.add('debug_mode')
        result.add('exec_logs')
        return result

    @classmethod
    def _export_light(cls):
        return super(RuleEngine, cls)._export_light() | {'context',
            'tables_used', 'tags'}

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

    @fields.depends('name', 'algorithm')
    def on_change_with_execution_code(self, name=None):
        return self.as_function(self.name, self.algorithm)

    @fields.depends('short_name', 'name')
    def on_change_with_short_name(self):
        if self.short_name:
            return self.short_name
        return coop_string.slugify(self.name)

    @classmethod
    def get_passing_test_cases(cls, instances, name):
        cursor = Transaction().cursor

        rule = cls.__table__()
        test_case = Pool().get('rule_engine.test_case').__table__()

        cursor.execute(*rule.join(test_case, 'LEFT OUTER', condition=(
                    (test_case.rule == rule.id) &
                    (test_case.last_passing_date == None))
                ).select(rule.id, Count(test_case.id),
                where=(rule.id.in_([x.id for x in instances])),
                group_by=rule.id))

        result = {}
        for rule_id, failed_test_case in cursor.fetchall():
            result[rule_id] = failed_test_case == 0
        return result

    @classmethod
    def search_passing_test_cases(cls, name, clause):
        test_case = Pool().get('rule_engine.test_case').__table__()
        query = test_case.select(test_case.rule,
            where=(test_case.last_passing_date == None),
            group_by=test_case.rule)

        if clause[2] is True:
            return [('id', 'not in', query)]
        elif clause[2] is False:
            return [('id', 'in', query)]
        return []

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
        elif (isinstance(error, pyflakes.messages.UndefinedName) and
                error.message_args[0] in self.allowed_functions()):
            return False
        else:
            return True

    def check_code(self):
        if Transaction().user == 0:
            return True
        errors = filter(lambda m: self.filter_errors(m),
            check_code(self.execution_code))
        if not errors:
            return True
        logging.getLogger('rule_engine').warning([
                x.message_args for x in errors])
        self.raise_user_error('invalid_code')

    def get_extra_data_for_on_change(self, existing_values):
        if not getattr(self, 'parameters', None):
            return None
        return dict([(elem.name, existing_values.get(
                        elem.name, None))
                for elem in self.parameters])

    def get_full_context_for_execution(self):
        base_context = self.context.get_context(self)
        self.add_rule_parameters_to_context(base_context)
        return base_context

    @staticmethod
    def execute_rule(rule_id, evaluation_context, **execution_kwargs):
        the_rule = Pool().get('rule_engine')(rule_id)
        result = the_rule.execute(evaluation_context, execution_kwargs)
        if result.has_errors:
            raise InternalRuleEngineError(
                'Impossible to evaluate parameter %s' % the_rule.short_name)
        return result.result

    @staticmethod
    def execute_table(table_id, evaluation_context, *dim_values):
        # evaluation_context is unused, but we need it so that all context
        # functions share the same prototype
        pool = Pool()
        TableCell = pool.get('table.cell')
        Table = pool.get('table')
        return TableCell.get(Table(table_id), *dim_values)

    @staticmethod
    def execute_param(param_id, evaluation_context):
        # evaluation_context is unused, but we need it so that all context
        # functions share the same prototype
        RuleParameter = Pool().get('rule_engine.rule_parameter')
        RuleEngine.raise_user_error('kwarg_expected',
            RuleParameter(param_id).name)

    def as_context(self, elem, kind, base_context):
        technical_name = self.get_translated_name(elem, kind)
        if kind == 'rule':
            base_context[technical_name] = functools.partial(
                self.execute_rule, elem.id)
        elif kind == 'table':
            base_context[technical_name] = functools.partial(
                self.execute_table, elem.id)
        elif kind == 'param':
            base_context[technical_name] = functools.partial(
                self.execute_param, elem.id)

    def add_rule_parameters_to_context(self, base_context):
        for elem in self.parameters:
            self.as_context(elem, 'param', base_context)
        for elem in self.tables_used:
            self.as_context(elem, 'table', base_context)
        for elem in self.rules_used:
            self.as_context(elem, 'rule', base_context)

    def prepare_context(self, evaluation_context, execution_kwargs):
        debug = Transaction().context.get('debug', True)
        pre_context = None
        if self.id >= 0 and not debug:
            pre_context = self._prepare_context_cache.get(self.id)
        if pre_context is None:
            pre_context = self.get_full_context_for_execution()
            if self.id >= 0 and not debug:
                self._prepare_context_cache.set(self.id, pre_context)
        exec_context = {'evaluation_context': evaluation_context}
        for k, v in pre_context.iteritems():
            if k in execution_kwargs:
                exec_context[k] = execution_kwargs.pop(k)
            else:
                exec_context[k] = functools.partial(v, evaluation_context)
        for k, v in execution_kwargs.iteritems():
            if 'param_%s' % k in exec_context:
                exec_context['param_%s' % k] = v
        evaluation_context['__result__'] = RuleEngineResult()
        if not debug:
            return exec_context
        for k, v in exec_context.iteritems():
            if k == 'evaluation_context':
                continue
            exec_context[k] = debug_wrapper(evaluation_context, v, k)
        return exec_context

    def compute(self, evaluation_context, execution_kwargs):
        with Transaction().set_context(debug=self.debug_mode or
                'force_debug_mode' in Transaction().context):
            context = self.prepare_context(evaluation_context,
                execution_kwargs)
            the_result = context['evaluation_context']['__result__']
            localcontext = {}
            try:
                comp = _compile_source_exec(self.execution_code)
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
                self.add_debug_log(the_result,
                    evaluation_context.get('date', None), exc)
                if self.debug_mode:
                    the_result.result = str(exc)
                    return the_result
                self.raise_user_error('bad_rule_computation', (self.name,
                        str(exc.args)))
        return the_result

    @staticmethod
    def as_function(rule_name, rule_algorithm):
        code = '\n'.join(' ' + l for l in rule_algorithm.splitlines())
        name = ('%s' % hash(rule_name)).replace('-', '_')
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
            res = ', '.join([coop_string.slugify(x, lower=False)
                for x in dimension_names])
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

    def add_debug_log(self, result, date, exc=None):
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
            rule_execution.calculation_date = date
            if exc:
                rule_execution.errors += '\n' + (
                    coop_string.slugify(self.name) + ' - ' + str(exc))
            rule_execution.save()
            try:
                transaction.cursor.commit()
            except DatabaseOperationalError:
                transaction.cursor.rollback()

    def execute(self, arguments, parameters=None):

        # We cannot use lambda in a loop
        def kwarg_function(value):
            return lambda: value

        parameters_as_func = {}
        for k, v in (parameters or {}).iteritems():
            parameters_as_func[k] = v if callable(v) else kwarg_function(v)
        result = self.compute(arguments, parameters_as_func)
        self.add_debug_log(result, arguments.get('date', None))
        return result


class Context(ModelView, ModelSQL, model.TaggedMixin):
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
                if element.type == 'folder':
                    pass
                elif element.translated_technical_name in names:
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
        base_context = {}
        for element in self.allowed_elements:
            element.as_context(base_context)
        return base_context

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
    type_string = type.translated('type')
    parent = fields.Many2One('rule_engine.function', 'Parent',
        ondelete='SET NULL')
    children = fields.One2Many('rule_engine.function', 'parent', 'Children',
        target_not_required=True)
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
            return
        self.translated_technical_name = \
            coop_string.slugify(self.description)

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

    def as_context(self, base_context):
        if self.translated_technical_name in base_context:
            return base_context
        pool = Pool()
        if self.type == 'function':
            namespace_obj = pool.get(self.namespace)
            base_context[self.translated_technical_name] = getattr(
                namespace_obj, self.name)
        for element in self.children:
            element.as_context(base_context)
        return base_context

    @fields.depends('rule')
    def on_change_with_translated_technical_name(self):
        if self.rule:
            return coop_string.slugify(self.rule.name)

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
        ast_node = ast.parse(rule.execution_code)
        func_finder.visit(ast_node)
        test_values = list(set([
            (n, n) for n in func_finder.functions
            if n not in (rule_name, 'Decimal')]))
        return test_values + [('', '')]

    @classmethod
    def default_override_value(cls):
        return True


class TestCase(ModelView, ModelSQL):
    'Test Case'
    __name__ = 'rule_engine.test_case'
    _rec_name = 'description'

    description = fields.Char('Description', required=True)
    rule = fields.Many2One('rule_engine', 'Rule', required=True,
        ondelete='CASCADE')
    expected_result = fields.Char('Expected Result')
    test_values = fields.One2Many('rule_engine.test_case.value', 'test_case',
        'Values', depends=['rule'], delete_missing=True,
        context={'rule_id': Eval('rule')})
    result_value = fields.Char('Result Value')
    result_warnings = fields.Text('Result Warnings')
    result_errors = fields.Text('Result Errors')
    result_info = fields.Text('Result Info')
    debug = fields.Text('Debug Info')
    low_debug = fields.Text('Low Level Debug Info')
    last_passing_date = fields.DateTime('Last passing run date')
    last_passing_date_str = fields.Function(
        fields.Char('Last Passing run date'),
        'on_change_with_last_passing_date_str')
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
            return self.rule.execute({}, test_context)

    @fields.depends('test_values', 'rule')
    def on_change_test_values(self):
        try:
            test_result = self.execute_test()
        except Exception as exc:
            self.result_value = 'ERROR: {}'.format(exc)
            self.result_info = self.result_warnings = self.result_errors = ''
            self.debug = self.low_debug = ''
            self.expected_result = self.result_value
            return
        if test_result == {}:
            return
        self.result_value = test_result.print_result()
        self.result_info = '\n'.join(test_result.print_info())
        self.result_warning = '\n'.join(test_result.print_warnings())
        self.result_errors = '\n'.join(test_result.print_errors())
        self.debug = '\n'.join(test_result.print_debug())
        self.low_debug = '\n'.join(test_result.print_low_level_debug())
        self.expected_result = str(test_result)

    @fields.depends('last_passing_date')
    def on_change_with_last_passing_date_str(self, name=None):
        return Pool().get('ir.date').datetime_as_string(self.last_passing_date)

    @staticmethod
    def order_last_passing_date_str(tables):
        table, _ = tables[None]
        return [Coalesce(table.last_passing_date, datetime.date.min)]

    @classmethod
    @TrytonModelView.button
    def recalculate(cls, instances):
        for elem in instances:
            elem.on_change_test_values()
        cls.save(instances)

    @classmethod
    @TrytonModelView.button
    def check_pass(cls, instances):
        passed, failed = [], []
        for elem in instances:
            prev_value = elem.expected_result
            elem.on_change_test_values()
            if elem.expected_result == prev_value:
                passed.append(elem)
            else:
                failed.append(elem)
        write_args = []
        for elems, date in [(passed, datetime.datetime.now()), (failed, None)]:
            if not elems:
                continue
            write_args += [elems, {'last_passing_date': date}]
        if write_args:
            cls.write(*write_args)

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
        errors = check_code(the_rule.execution_code)
        result = []
        allowed_functions = the_rule.allowed_functions()
        for error in errors:
            if (isinstance(error, pyflakes.messages.UndefinedName) and
                    error.message_args[0] in allowed_functions):
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
    kind_string = kind.translated('kind')
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
            return coop_string.slugify(self.name)

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


class InitTestCaseFromExecutionLog(Wizard):
    'Init Test Case From Execution Log'

    __name__ = 'rule_engine.test_case.init'

    start_state = 'select_values'
    select_values = StateView('rule_engine.test_case',
        'rule_engine.test_case_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Accept', 'create_test_case', 'tryton-go-next')])
    create_test_case = StateTransition()

    @classmethod
    def __setup__(cls):
        super(InitTestCaseFromExecutionLog, cls).__setup__()
        cls._error_messages.update({
                'rule_engine_log_expected': 'This wizard should be run from'
                'a rule engine execution log selected',
                })

    def filter_override(self, method_name):
        if method_name.startswith('table_'):
            return False
        elif method_name.startswith('rule_'):
            return False
        elif method_name in ('add_info', 'add_error', 'add_warning',
                'add_debug'):
            return False
        return True

    def default_select_values(self, name):
        active_id = Transaction().context.get('active_id')
        active_model = Transaction().context.get('active_model')
        if active_model != 'rule_engine.log':
            self.raise_user_error('rule_engine_log_expected')
        pool = Pool()
        log = pool.get(active_model)(active_id)
        calls = [x.split('|&|') for x in log.calls.splitlines()]
        test_values = [{
                'rule': log.rule.id,
                'name': x[0],
                'value': x[3],
                'override_value': self.filter_override(x[0]),
                } for x in calls]
        description = ', '.join(['result: %s' % log.result] + ['%s: %s' % (
                    x['name'], x['value'])
                for x in test_values if x['override_value']])
        return {
            'expected_result': '[%s, [%s], [%s], [%s]]' % (
                log.result, log.errors, log.warnings, log.info),
            'result_value': log.result,
            'result_warnings': log.warnings,
            'result_errors': log.errors,
            'result_infos': log.info,
            'debug': log.debug,
            'rule': log.rule.id,
            'low_debug': log.low_level_debug,
            'rule_text': log.rule.algorithm,
            'test_values': test_values,
            'description': description,
            }

    def transition_create_test_case(self):
        self.select_values.save()
        return 'end'


class ValidateRuleTestCases(Wizard):
    'Validate Rule Test Cases'

    __name__ = 'rule_engine.validate_test_cases'

    start_state = 'run_test_cases'
    run_test_cases = StateTransition()

    def transition_run_test_cases(self):
        rule_ids = Transaction().context.get('active_ids')
        TestCase = Pool().get('rule_engine.test_case')
        TestCase.check_pass(TestCase.search([
                    ('rule', 'in', rule_ids)]))
        return 'end'

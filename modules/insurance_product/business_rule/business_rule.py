#-*- coding:utf-8 -*-
import copy
import json
import functools

import pyflakes.messages

from trytond.pool import PoolMeta
from trytond.pyson import Eval, Or
from trytond.transaction import Transaction

from trytond.modules.coop_utils import model, utils, fields
from trytond.modules.insurance_product.product import CONFIG_KIND
from trytond.modules.insurance_product.product import Templated, GetResult

STATE_SIMPLE = Eval('config_kind') != 'advanced'
STATE_ADVANCED = Eval('config_kind') != 'simple'
STATE_SUB_SIMPLE = Eval('sub_elem_config_kind') != 'simple'

__all__ = [
    'RuleEngineComplementaryDataRelation',
    'RuleEngine',
    'BusinessRuleRoot',
]


class RuleEngineComplementaryDataRelation(model.CoopSQL):
    'Rule engine to complementary data relation'

    __name__ = 'ins_product.rule_engine_complementary_data_relation'

    rule = fields.Many2One('rule_engine', 'Rule', ondelete='CASCADE')
    complementary_data = fields.Many2One(
        'ins_product.complementary_data_def', 'Complementary Data',
        ondelete='RESTRICT')


class RuleEngine():
    'Rule Engine'

    __metaclass__ = PoolMeta
    __name__ = 'rule_engine'

    complementary_parameters = fields.Many2Many(
        'ins_product.rule_engine_complementary_data_relation',
        'rule', 'complementary_data', 'Complementary Parameters',
        domain=[('kind', '=', 'rule_engine')],
        on_change=['context', 'complementary_parameters'])

    @classmethod
    def __setup__(cls):
        super(RuleEngine, cls).__setup__()
        cls.context = copy.copy(cls.context)
        cls.context.on_change.append('complementary_parameters')

    def on_change_complementary_parameters(self):
        return {
            'data_tree': self.get_data_tree(None) if self.context else '[]'}

    def get_data_tree(self, name):
        if not (hasattr(self, 'complementary_parameters') and
                self.complementary_parameters):
            return super(RuleEngine, self).get_data_tree(name)
        tmp_result = [e.as_tree() for e in self.context.allowed_elements]
        tmp_node = {}
        tmp_node['name'] = 'x-y-z'
        tmp_node['translated'] = 'x-y-z'
        tmp_node['fct_args'] = ''
        tmp_node['description'] = 'X-Y-Z'
        tmp_node['type'] = 'folder'
        tmp_node['long_description'] = ''
        tmp_node['children'] = []
        for elem in self.complementary_parameters:
            param_node = {}
            param_node['name'] = elem.string
            param_node['translated'] = 'rule_engine_parameter_%s' % elem.name
            param_node['fct_args'] = ''
            param_node['description'] = elem.string
            param_node['type'] = 'function'
            param_node['long_description'] = ''
            param_node['children'] = []
            tmp_node['children'].append(param_node)
        tmp_result.append(tmp_node)
        return json.dumps(tmp_result)

    @classmethod
    def get_complementary_parameter_value(cls, args, schema_name):
        return args['_caller'].get_rule_complementary_data(schema_name)

    def get_context_for_execution(self):
        result = super(RuleEngine, self).get_context_for_execution()
        if not (hasattr(self, 'complementary_parameters') and
                self.complementary_parameters):
            return result
        for schema in self.complementary_parameters:
            result['rule_engine_parameter_%s' % schema.name] = \
                functools.partial(
                    self.get_complementary_parameter_value,
                    result, schema.name)
        return result

    def filter_errors(self, error):
        result = super(RuleEngine, self).filter_errors(error)
        if not result and isinstance(error, pyflakes.messages.UndefinedName):
            if error.message_args[0][:24] == '_rule_complementary_data':
                if error.message_args[0][25:] in self._rule_complementary_data:
                    return True
        return False

    @property
    def _allowed_functions(self):
        result = super(RuleEngine, self).allowed_functions
        result += [
            '_rule_complementary_data%s' % elem.name
            for elem in self._rule_complementary_data]
        return result


class BusinessRuleRoot(model.CoopView, GetResult, Templated):
    'Business Rule Root'

    __name__ = 'ins_product.business_rule_root'

    offered = fields.Reference('Offered', selection='get_offered_models')
    start_date = fields.Date('From Date', required=True)
    end_date = fields.Date('To Date')
    config_kind = fields.Selection(
        CONFIG_KIND, 'Conf. kind', required=True)
    rule = fields.Many2One(
        'rule_engine', 'Rule Engine', states={'invisible': STATE_SIMPLE},
        depends=['config_kind'])
    view_rec_name = fields.Function(
        fields.Char('Name'),
        'get_rec_name')
    rule_complementary_data = fields.Dict(
        'ins_product.complementary_data_def', 'Rule Complementary Data',
        on_change_with=['rule', 'rule_complementary_data'],
        states={'invisible':
            Or(STATE_SIMPLE, ~Eval('rule_complementary_data'))})

    @classmethod
    def __setup__(cls):
        super(BusinessRuleRoot, cls).__setup__()
        cls.template = copy.copy(cls.template)
        cls.template.model_name = cls.__name__
        if hasattr(cls, '_order'):
            cls._order.insert(0, ('start_date', 'ASC'))
        if hasattr(cls, '_constraints'):
            cls._constraints += [('check_dates', 'businessrule_overlaps')]
        if hasattr(cls, '_error_messages'):
            cls._error_messages.update({
                'businessrule_overlaps':
                'You can not have 2 business rules that overlaps!'})

    def get_rule_result(self, args):
        if self.rule:
            res, mess, errs = utils.execute_rule(self, self.rule, args)
            return res, mess + errs

    def on_change_with_rule_complementary_data(self):
        if not (hasattr(self, 'rule') and self.rule):
            return {}
        if not (hasattr(self.rule, 'complementary_parameters') and
                self.rule.complementary_parameters):
            return {}
        return dict([
            (elem.name, self.rule_complementary_data.get(
                elem.name, elem.get_default_value(None)))
            for elem in self.rule.complementary_parameters])

    def get_rule_complementary_data(self, schema_name):
        if not (hasattr(self, 'rule_complementary_data') and
                self.rule_complementary_data):
            return None
        return self.rule_complementary_data.get(schema_name, None)

    def get_simple_result(self, args):
        return None, None

    def give_me_result(self, args):
        if self.config_kind == 'advanced':
            return self.get_rule_result(args)
        else:
            return self.get_simple_result(args)

    @staticmethod
    def default_config_kind():
        return 'simple'

    def get_offered(self):
        return self.generic_rule.get_offered()

    @classmethod
    def get_offered_models(cls):
        module_name = utils.get_module_name(cls)
        return [
            x for x in utils.get_descendents('ins_product.offered')
            if module_name in x[0]]

    @classmethod
    def recreate_rather_than_update(cls):
        return True

    def get_rec_name(self, name=None):
        if self.config_kind == 'advanced' and self.rule:
            return self.rule.get_rec_name()
        return self.get_simple_rec_name()

    def get_simple_rec_name(self):
        return ''

    @staticmethod
    def default_start_date():
        res = Transaction().context.get('start_date')
        if not res:
            date = utils.today()
            res = date
        return res

    def check_dates(self):
        cursor = Transaction().cursor
        cursor.execute(
            'SELECT id '
            'FROM ' + self._table + ' '
            'WHERE ((start_date <= %s AND end_date >= %s) '
            '        OR (start_date <= %s AND end_date >= %s) '
            '        OR (start_date >= %s AND end_date <= %s)) '
            '    AND offered = %s'
            '    AND id != %s', (
            self.start_date, self.start_date,
            self.end_date, self.end_date,
            self.start_date, self.end_date,
            '%s,%s' % (self.offered.__class__.__name__, self.offered.id),
            self.id))
        if cursor.fetchone():
            return False
        return True

    @classmethod
    def copy(cls, rules, default):
        return super(BusinessRuleRoot, cls).copy(rules, default=default)

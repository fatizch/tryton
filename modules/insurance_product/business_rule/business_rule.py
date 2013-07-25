#-*- coding:utf-8 -*-
import copy

from trytond.pool import PoolMeta
from trytond.pyson import Eval, Or
from trytond.transaction import Transaction

from trytond.modules.coop_utils import model, utils, fields
from trytond.modules.offered.offered import CONFIG_KIND, Templated, GetResult

STATE_SIMPLE = Eval('config_kind') != 'advanced'
STATE_ADVANCED = Eval('config_kind') != 'simple'
STATE_SUB_SIMPLE = Eval('sub_elem_config_kind') != 'simple'

__all__ = [
    'RuleEngineParameter',
    'RuleEngine',
    'DimensionDisplayer',
    'BusinessRuleRoot',
]


class RuleEngineParameter():
    'Rule Engine Parameter'

    __metaclass__ = PoolMeta
    __name__ = 'rule_engine.parameter'

    the_complementary_data = fields.Many2One('offered.complementary_data_def',
        'Complementary Parameters', domain=[('kind', '=', 'rule_engine')],
        ondelete='RESTRICT', on_change=['the_complementary_data'],
        states={'invisible': Eval('kind', '') != 'rule_compl',
            'required': Eval('kind', '') == 'rule_compl'})
    rule_complementary_data = fields.Dict(
        'offered.complementary_data_def', 'Rule Complementary Data',
        on_change_with=['the_rule', 'rule_complementary_data'],
        states={'invisible': Or(
                Eval('kind', '') != 'rule', ~Eval('rule_complementary_data'))})
    external_complementary_data = fields.Many2One(
        'offered.complementary_data_def', 'External Complementary Data',
        domain=[('kind', '!=', 'rime_engine')], ondelete='RESTRICT',
        on_change=['external_complementary_data'],
        states={'invisible': Eval('kind', '') != 'compl',
            'required': Eval('kind', '') == 'compl'})

    @classmethod
    def __setup__(cls):
        super(RuleEngineParameter, cls).__setup__()
        cls.kind = copy.copy(cls.kind)
        cls.kind.selection.append(('rule_compl', 'Rule Complementary Data'))
        cls.kind.selection.append(('compl', 'External Complementary Data'))
        cls.kind.selection = list(set(cls.kind.selection))
        cls.the_rule = copy.copy(cls.the_rule)
        if not cls.the_rule.depends:
            cls.the_rule.depends = []
        cls.the_rule.depends.append('rule_complementary_data')

    def on_change_kind(self):
        result = super(RuleEngineParameter, self).on_change_kind()
        if hasattr(self, 'kind') and self.kind != 'rule_compl':
            result['the_complementary_data'] = None
        if hasattr(self, 'kind') and self.kind != 'compl':
            result['external_complementary_data'] = None
        return result

    @classmethod
    def get_complementary_parameter_value(cls, args, schema_name):
        return args['_caller'].get_rule_complementary_data(schema_name)

    def get_rule_complementary_data(self, schema_name):
        if not (hasattr(self, 'rule_complementary_data') and
                self.rule_complementary_data):
            return None
        return self.rule_complementary_data.get(schema_name, None)

    def get_lowest_level_object(self, args):
        '''This method to be overriden in different modules sets the lowest
        object from where to search data. The object will level up itself if it
        doesn't find the good information at its own level'''
        if 'option' in args:
            return args['option']
        if 'contract' in args:
            return args['contract']

    def get_external_complementary_data(self, args):
        from_object = self.get_lowest_level_object(args)
        return self.external_complementary_data.get_complementary_data_value(
            from_object, self.external_complementary_data.string.name,
            args['date'])

    def as_context(self, evaluation_context, context, forced_value):
        super(RuleEngineParameter, self).as_context(
            evaluation_context, context, forced_value)
        technical_name = self.get_translated_technical_name()
        if technical_name in context:
            # Looks like the value was forced
            return context
        debug_wrapper = self.get_wrapper_func(context)
        if self.kind == 'rule_compl':
            context[technical_name] = debug_wrapper(
                lambda: self.get_complementary_parameter_value(
                    evaluation_context, self.the_complementary_data.name))
        elif self.kind == 'compl':
            context[technical_name] = debug_wrapper(
                lambda: self.get_external_complementary_data(
                    evaluation_context))
        return context

    def on_change_with_rule_complementary_data(self):
        if not (hasattr(self, 'the_rule') and self.the_rule):
            return None
        return self.the_rule.get_complementary_data_for_on_change(
            self.rule_complementary_data)

    def on_change_the_complementary_data(self):
        result = {}
        if not (hasattr(self, 'the_complementary_data') and
                self.the_complementary_data):
            return result
        result['code'] = self.the_complementary_data.name
        result['name'] = self.the_complementary_data.string
        return result

    def on_change_external_complementary_data(self):
        result = {}
        if not (hasattr(self, 'external_complementary_data') and
                self.external_complementary_data):
            return result
        result['code'] = self.external_complementary_data.name
        result['name'] = self.external_complementary_data.string
        return result

    @classmethod
    def build_root_node(cls, kind):
        tmp_node = super(RuleEngineParameter, cls).build_root_node(kind)
        if kind == 'rule_compl':
            tmp_node['name'] = 'rule_compl'
            tmp_node['translated'] = 'rule_compl'
            tmp_node['fct_args'] = ''
            tmp_node['description'] = 'Rule Complementary Data'
            tmp_node['type'] = 'folder'
            tmp_node['long_description'] = ''
            tmp_node['children'] = []
        elif kind == 'compl':
            tmp_node['name'] = 'compl'
            tmp_node['translated'] = 'compl'
            tmp_node['fct_args'] = ''
            tmp_node['description'] = 'External Complementary Data'
            tmp_node['type'] = 'folder'
            tmp_node['long_description'] = ''
            tmp_node['children'] = []
        return tmp_node


class RuleEngine():
    'Rule Engine'

    __metaclass__ = PoolMeta
    __name__ = 'rule_engine'

    rule_external_compl_datas = fields.One2ManyDomain('rule_engine.parameter',
        'parent_rule', 'Rule External Complementary Data',
        domain=[('kind', '=', 'compl')])
    rule_compl_datas = fields.One2ManyDomain('rule_engine.parameter',
        'parent_rule', 'Rule Complementary Datas',
        domain=[('kind', '=', 'rule_compl')])

    @classmethod
    def __setup__(cls):
        super(RuleEngine, cls).__setup__()

    @classmethod
    def _export_skips(cls):
        result = super(RuleEngine, cls)._export_skips()
        result.add('rule_external_compl_datas')
        result.add('rule_compl_datas')
        return result

    def get_complementary_data_for_on_change(self, existing_values):
        if not (hasattr(self, 'rule_parameters') and
                self.rule_parameters):
            return None
        return dict([
                (elem.the_complementary_data.name, existing_values.get(
                        elem.the_complementary_data.name,
                        elem.the_complementary_data.get_default_value(None)))
                for elem in self.rule_parameters
                if elem.kind == 'complementary_data'])

    def on_change_rule_compl_datas(self):
        return self.on_change_rule_parameters()

    def on_change_rule_external_compl_datas(self):
        return self.on_change_rule_parameters()


class DimensionDisplayer():
    'Dimension Displayer'

    __metaclass__ = PoolMeta
    __name__ = 'table.dimension_displayer'

    complementary_data = fields.Many2One('offered.complementary_data_def',
        'Complementary Data', domain=[('type_', '=', 'selection')], states={
            'invisible': Eval('input_mode', '') != 'compl_data'},
        on_change=['input_mode', 'complementary_data'])

    @classmethod
    def __setup__(cls):
        super(DimensionDisplayer, cls).__setup__()
        cls.input_mode = copy.copy(cls.input_mode)
        cls.input_mode.selection.append(('compl_data', 'Complementary data'))

    def on_change_complementary_data(self):
        if self.input_mode == 'compl_data' and self.complementary_data:
            return {'converted_text': '\n'.join([x.split(':')[0] for x in
                self.complementary_data.selection.split('\n')])}
        else:
            return {'complementary_data': None}

    def on_change_input_mode(self):
        result = super(DimensionDisplayer, self).on_change_input_mode()
        if self.input_mode != 'compl_data':
            result.update({'complementary_data': None})
            return result
        self.input_text = ''
        result = self.on_change_input_text()
        result.update({'input_text': ''})
        return result

    def convert_values(self):
        if self.input_mode == 'compl_data':
            return '\n'.join([x.split(':')[0] for x in
                self.complementary_data.selection.split('\n')])
        return super(DimensionDisplayer, self).convert_values()


class BusinessRuleRoot(model.CoopView, GetResult, Templated):
    'Business Rule Root'

    __name__ = 'ins_product.business_rule_root'

    offered = fields.Reference('Offered',
        selection=[
            ('offered.product', 'Product'),
            ('offered.coverage', 'Coverage'),
            ('ins_product.benefit', 'Benefit')
            ])
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
        'offered.complementary_data_def', 'Rule Complementary Data',
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
            return utils.execute_rule(self, self.rule, args)

    def on_change_with_rule_complementary_data(self):
        if not (hasattr(self, 'rule') and self.rule):
            return {}
        return self.rule.get_complementary_data_for_on_change(
            self.rule_complementary_data)

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
        request = 'SELECT id ' + \
            'FROM ' + self._table + ' ' + \
            'WHERE ((start_date <= %s AND end_date >= %s) ' + \
            '        OR (start_date <= %s AND end_date >= %s) ' + \
            '        OR (start_date >= %s AND end_date <= %s)) ' + \
            '    AND offered = %s' + \
            '    AND id != %s'

        #offered depends if the link is a reference link or a M2O
        if hasattr(self.__class__.offered, 'selection'):
            offered = '%s,%s' % (self.offered.__class__.__name__,
                self.offered.id)
        else:
            offered = self.offered.id
        args = (
            self.start_date, self.start_date,
            self.end_date, self.end_date,
            self.start_date, self.end_date,
            offered,
            self.id)
        cursor.execute(request, args)
        if cursor.fetchone():
            return False
        return True

    @classmethod
    def copy(cls, rules, default):
        return super(BusinessRuleRoot, cls).copy(rules, default=default)

#-*- coding:utf-8 -*-
import copy

from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, Or
from trytond.transaction import Transaction

from trytond.modules.cog_utils import model, utils, fields
from trytond.modules.rule_engine import RuleEngineResult
from trytond.modules.offered.offered import CONFIG_KIND, Templated, GetResult

STATE_SIMPLE = Eval('config_kind') != 'advanced'
STATE_ADVANCED = Eval('config_kind') != 'simple'
STATE_SUB_SIMPLE = Eval('sub_elem_config_kind') != 'simple'

__metaclass__ = PoolMeta
__all__ = [
    'RuleEngineParameter',
    'RuleEngine',
    'TableManageDimensionShowDimension',
    'BusinessRuleRoot',
    ]


class RuleEngineParameter:
    __name__ = 'rule_engine.parameter'

    extra_data_def = fields.Many2One('extra_data', 'Extra Parameters',
        domain=[('kind', '=', 'rule_engine')],
        ondelete='RESTRICT', on_change=['extra_data_def'], states={
            'invisible': Eval('kind', '') != 'rule_compl',
            'required': Eval('kind', '') == 'rule_compl',
            })
    rule_extra_data = fields.Dict('extra_data', 'Rule Extra Data',
        on_change_with=['the_rule', 'rule_extra_data'],
        states={'invisible': Or(
                Eval('kind', '') != 'rule', ~Eval('rule_extra_data'))})
    external_extra_data_def = fields.Many2One('extra_data',
        'External Extra Data', domain=[('kind', '!=', 'rime_engine')],
        ondelete='RESTRICT', on_change=['external_extra_data_def'],
        states={
            'invisible': Eval('kind', '') != 'compl',
            'required': Eval('kind', '') == 'compl',
            })

    @classmethod
    def __setup__(cls):
        super(RuleEngineParameter, cls).__setup__()
        cls.kind = copy.copy(cls.kind)
        cls.kind.selection.append(('rule_compl', 'Rule Extra Data'))
        cls.kind.selection.append(('compl', 'External Extra Data'))
        cls.kind.selection = list(set(cls.kind.selection))
        cls.the_rule = copy.copy(cls.the_rule)
        if not cls.the_rule.depends:
            cls.the_rule.depends = []
        cls.the_rule.depends.append('rule_extra_data')

    def on_change_kind(self):
        result = super(RuleEngineParameter, self).on_change_kind()
        if hasattr(self, 'kind') and self.kind != 'rule_compl':
            result['extra_data_def'] = None
        if hasattr(self, 'kind') and self.kind != 'compl':
            result['external_extra_data_def'] = None
        return result

    @classmethod
    def get_complementary_parameter_value(cls, args, schema_name):
        return args['_extra_data'][schema_name]

    def get_external_extra_data_def(self, args):
        OfferedSet = Pool().get('rule_engine.runtime')
        from_object = OfferedSet.get_lowest_level_object(args)
        return self.external_extra_data_def.get_extra_data_value(
            from_object, self.external_extra_data_def.name,
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
                    evaluation_context, self.extra_data_def.name))
        elif self.kind == 'compl':
            context[technical_name] = debug_wrapper(
                lambda: self.get_external_extra_data_def(
                    evaluation_context))
        return context

    def on_change_with_rule_extra_data(self):
        if not (hasattr(self, 'the_rule') and self.the_rule):
            return None
        return self.the_rule.get_extra_data_for_on_change(
            self.rule_extra_data)

    def on_change_extra_data_def(self):
        result = {}
        if not (hasattr(self, 'extra_data_def') and
                self.extra_data_def):
            return result
        result['code'] = self.extra_data_def.name
        result['name'] = self.extra_data_def.string
        return result

    def on_change_external_extra_data_def(self):
        result = {}
        if not (hasattr(self, 'external_extra_data_def') and
                self.external_extra_data_def):
            return result
        result['code'] = self.external_extra_data_def.name
        result['name'] = self.external_extra_data_def.string
        return result

    @classmethod
    def build_root_node(cls, kind):
        tmp_node = super(RuleEngineParameter, cls).build_root_node(kind)
        if kind == 'rule_compl':
            tmp_node['name'] = 'rule_compl'
            tmp_node['translated'] = 'rule_compl'
            tmp_node['fct_args'] = ''
            tmp_node['description'] = 'Rule Extra Data'
            tmp_node['type'] = 'folder'
            tmp_node['long_description'] = ''
            tmp_node['children'] = []
        elif kind == 'compl':
            tmp_node['name'] = 'compl'
            tmp_node['translated'] = 'compl'
            tmp_node['fct_args'] = ''
            tmp_node['description'] = 'External Extra Data'
            tmp_node['type'] = 'folder'
            tmp_node['long_description'] = ''
            tmp_node['children'] = []
        return tmp_node


class RuleEngine:
    __name__ = 'rule_engine'

    rule_external_extra_datas = fields.One2ManyDomain('rule_engine.parameter',
        'parent_rule', 'Extra Data', domain=[('kind', '=', 'compl')],
        states={'invisible': Or(~Eval('extra_data'),
                Eval('extra_data_kind') != 'compl')})
    rule_extra_datas = fields.One2ManyDomain('rule_engine.parameter',
        'parent_rule', 'Rule Parameter', domain=[('kind', '=', 'rule_compl')],
        states={'invisible': Or(~Eval('extra_data'),
                Eval('extra_data_kind') != 'rule_compl')})

    @classmethod
    def __setup__(cls):
        super(RuleEngine, cls).__setup__()
        cls.extra_data_kind = copy.copy(cls.extra_data_kind)
        cls.extra_data_kind.selection.extend([('compl', 'Extra Data'),
                ('rule_compl', 'Rule Parameter')])
        cls.extra_data_kind.selection = list(set(
                cls.extra_data_kind.selection))

    @classmethod
    def _export_skips(cls):
        result = super(RuleEngine, cls)._export_skips()
        result.add('rule_external_extra_datas')
        result.add('rule_extra_datas')
        return result

    def get_extra_data_for_on_change(self, existing_values):
        if not (hasattr(self, 'rule_parameters') and
                self.rule_parameters):
            return None
        return dict([
                (elem.extra_data_def.name, existing_values.get(
                        elem.extra_data_def.name,
                        elem.extra_data_def.get_default_value(None)))
                for elem in self.rule_extra_datas])

    def on_change_rule_extra_datas(self):
        return self.on_change_rule_parameters()

    def on_change_rule_external_extra_datas(self):
        return self.on_change_rule_parameters()


class TableManageDimensionShowDimension:
    __name__ = 'table.manage_dimension.show.dimension'

    extra_data = fields.Many2One('extra_data', 'Extra Data',
        domain=[('type_', '=', 'selection')], states={
            'invisible': Eval('input_mode', '') != 'extra_data',
            }, on_change=['input_mode', 'extra_data'])

    @classmethod
    def __setup__(cls):
        super(TableManageDimensionShowDimension, cls).__setup__()
        cls.input_mode = copy.copy(cls.input_mode)
        cls.input_mode.selection.append(('extra_data', 'Complementary data'))

    def on_change_extra_data(self):
        if self.input_mode == 'extra_data' and self.extra_data:
            return {'converted_text': '\n'.join([x.split(':')[0] for x in
                        self.extra_data.selection.split('\n')])}
        else:
            return {'extra_data': None}

    def on_change_input_mode(self):
        result = super(TableManageDimensionShowDimension,
            self).on_change_input_mode()
        if self.input_mode != 'extra_data':
            result.update({'extra_data': None})
            return result
        self.input_text = ''
        result = self.on_change_input_text()
        result.update({'input_text': ''})
        return result

    def convert_values(self):
        if self.input_mode == 'extra_data':
            return '\n'.join([x.split(':')[0] for x in
                self.extra_data.selection.split('\n')])
        return super(TableManageDimensionShowDimension, self).convert_values()


class BusinessRuleRoot(model.CoopView, GetResult, Templated):
    'Business Rule Root'

    __name__ = 'offered.business_rule_root'

    offered = fields.Reference('Offered', selection=[
            ('offered.product', 'Product'),
            ('offered.option.description', 'Option Description'),
            ], states={'required': True})
    start_date = fields.Date('From Date', required=True)
    end_date = fields.Date('To Date')
    config_kind = fields.Selection(CONFIG_KIND, 'Conf. kind', required=True)
    rule = fields.Many2One('rule_engine', 'Rule Engine',
        states={'invisible': STATE_SIMPLE},
        depends=['config_kind'], ondelete='RESTRICT')
    view_rec_name = fields.Function(
        fields.Char('Name'),
        'get_rec_name')
    rule_extra_data = fields.Dict('extra_data', 'Rule Extra Data',
        on_change_with=['rule', 'rule_extra_data'],
        states={'invisible':
            Or(STATE_SIMPLE, ~Eval('rule_extra_data'))})

    @classmethod
    def __setup__(cls):
        super(BusinessRuleRoot, cls).__setup__()
        cls.template = copy.copy(cls.template)
        cls.template.model_name = cls.__name__
        if hasattr(cls, '_order'):
            cls._order.insert(0, ('start_date', 'ASC'))
        if hasattr(cls, '_error_messages'):
            cls._error_messages.update({
                'businessrule_overlaps':
                'You can not have 2 business rules that overlaps!'})

    def get_rule_result(self, args):
        if self.rule:
            return self.rule.execute(args, self.rule_extra_data)

    def on_change_with_rule_extra_data(self):
        if not (hasattr(self, 'rule') and self.rule):
            return {}
        return self.rule.get_extra_data_for_on_change(
            self.rule_extra_data)

    def get_rule_extra_data(self, schema_name):
        if not (hasattr(self, 'rule_extra_data') and
                self.rule_extra_data):
            return None
        return self.rule_extra_data.get(schema_name, None)

    def get_simple_result(self, args):
        return None

    def give_me_result(self, args):
        if self.config_kind == 'advanced':
            return self.get_rule_result(args)
        else:
            return RuleEngineResult(self.get_simple_result(args))

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
        # TODO : use class method to validate as a group
        cursor = Transaction().cursor
        table = self.__table__()
        #offered depends if the link is a reference link or a M2O
        if hasattr(self.__class__.offered, 'selection'):
            offered = '%s,%s' % (self.offered.__class__.__name__,
                self.offered.id)
        else:
            offered = self.offered.id
        request = table.select(table.id,
            where=((table.start_date <= self.start_date and table.end_date >=
                    self.start_date)
                | (table.start_date <= self.end_date and table.end_date >=
                    self.end_date)
                | (table.start_date <= self.start_date and table.end_date <=
                    self.end_date))
                & (table.offered != offered) & (table.id != self.id))
        cursor.execute(*request)
        if cursor.fetchone():
            self.raise_user_error('businessrule_overlaps')

    @classmethod
    def validate(cls, rules):
        super(BusinessRuleRoot, cls).validate(rules)
        for rule in rules:
            rule.check_dates

    @classmethod
    def copy(cls, rules, default):
        return super(BusinessRuleRoot, cls).copy(rules, default=default)

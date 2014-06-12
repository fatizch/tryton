#-*- coding:utf-8 -*-
from trytond.pool import PoolMeta
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
    'BusinessRuleRoot',
    ]


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
    rule_extra_data = fields.Dict('rule_engine.rule_parameter',
        'Rule Extra Data', states={'invisible':
            Or(STATE_SIMPLE, ~Eval('rule_extra_data'))})

    @classmethod
    def __setup__(cls):
        super(BusinessRuleRoot, cls).__setup__()
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

    @fields.depends('rule', 'rule_extra_data')
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

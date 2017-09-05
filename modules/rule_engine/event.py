# encoding: utf-8
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.pyson import Bool, Or, Eval

from rule_engine import get_rule_mixin
from trytond.modules.coog_core import utils, fields


__all__ = [
    'EventTypeAction',
    ]


class EventTypeAction(get_rule_mixin('filter_rule', 'Filter Rule')):
    __metaclass__ = PoolMeta
    __name__ = 'event.type.action'

    @classmethod
    def __setup__(cls):
        super(EventTypeAction, cls).__setup__()
        pyson_invisible_state = cls.pyson_condition.states['invisible']
        cls.pyson_condition.states['invisible'] = Or(pyson_invisible_state,
            Bool(Eval('filter_rule')))
        cls.pyson_condition.depends.append('filter_rule')
        cls.filter_rule.states['invisible'] = Bool(Eval('pyson_condition'))
        cls.filter_rule.depends.append('pyson_condition')
        cls.filter_rule.domain = [
            ('type_', '=', 'event_filter')]
        cls.filter_rule_extra_data.states['invisible'] = ~Eval('filter_rule')

    def filter_objects(self, objects):
        objects = super(EventTypeAction, self).filter_objects(objects)
        if not self.filter_rule:
            return objects
        context_ = {'event_objects': objects, 'date': utils.today()}
        return self.calculate_filter_rule(context_)

    @fields.depends('pyson_condition')
    def on_change_pyson_condition(self):
        self.filter_rule = None

    @fields.depends('filter_rule')
    def on_change_filter_rule(self):
        if self.filter_rule:
            self.pyson_condition = ''

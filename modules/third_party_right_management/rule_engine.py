# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import PoolMeta
from trytond.modules.coog_core import fields


class RuleEngine(metaclass=PoolMeta):
    __name__ = 'rule_engine'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.type_.selection.append(
            ('third_party_management', 'Third Party Management'))

    @fields.depends('type_')
    def on_change_with_result_type(self, name=None):
        if self.type_ == 'third_party_management':
            return 'dict'
        return super().on_change_with_result_type(name)


class RuleTools(metaclass=PoolMeta):
    __name__ = 'rule_engine.runtime'

    @classmethod
    def _re_event_code(cls, args):
        return args.get('event_code')

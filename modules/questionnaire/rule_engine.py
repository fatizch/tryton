# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

from trytond.modules.coog_core import fields

__all__ = [
    'RuleEngine',
    ]


class RuleEngine(metaclass=PoolMeta):
    __name__ = 'rule_engine'

    @classmethod
    def __setup__(cls):
        super(RuleEngine, cls).__setup__()
        cls.type_.selection.append(('questionnaire', 'Questionnaire'))

    @fields.depends('type_')
    def on_change_with_result_type(self, name=None):
        if self.type_ == 'questionnaire':
            return 'list'
        return super(RuleEngine, self).on_change_with_result_type(name)

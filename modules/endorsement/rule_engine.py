# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.modules.coog_core import fields


__metaclass__ = PoolMeta
__all__ = [
    'RuleEngine',
    ]


class RuleEngine:
    __name__ = 'rule_engine'

    @classmethod
    def __setup__(cls):
        super(RuleEngine, cls).__setup__()
        cls.type_.selection.append(('endorsement_start', 'Endorsement Start'))

    @fields.depends('type_')
    def on_change_with_result_type(self, name=None):
        if self.type_ == 'endorsement_start':
            return 'boolean'
        return super(RuleEngine, self).on_change_with_result_type(name)

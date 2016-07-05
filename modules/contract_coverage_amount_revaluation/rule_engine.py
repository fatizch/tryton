# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

__metaclass__ = PoolMeta
__all__ = [
    'RuleEngine',
    ]


class RuleEngine:
    __name__ = 'rule_engine'

    @classmethod
    def __setup__(cls):
        super(RuleEngine, cls).__setup__()
        cls.type_.selection.append(('coverage_amount_revaluation',
            'Coverage Amount Revaluation'))

    def on_change_with_result_type(self, name=None):
        if self.type_ == 'coverage_amount_revaluation':
            return 'decimal'
        return super(RuleEngine, self).on_change_with_result_type(name)

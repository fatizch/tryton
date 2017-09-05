# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

from trytond.modules.coog_core import fields

__all__ = [
    'RuleEngine',
    'RuleEngineRuntime',
    ]


class RuleEngine:
    __metaclass__ = PoolMeta
    __name__ = 'rule_engine'

    @classmethod
    def __setup__(cls):
        super(RuleEngine, cls).__setup__()
        cls.type_.selection.append(('coverage_amount_revaluation',
            'Coverage Amount Revaluation'))

    @fields.depends('type_')
    def on_change_with_result_type(self, name=None):
        if self.type_ == 'coverage_amount_revaluation':
            return 'decimal'
        return super(RuleEngine, self).on_change_with_result_type(name)


class RuleEngineRuntime:
    __metaclass__ = PoolMeta
    __name__ = 'rule_engine.runtime'

    @classmethod
    def _re_get_base_coverage_amount(cls, args):
        option = cls.get_option(args)
        date = args['date']
        for version in reversed(option.versions):
            if version.start and version.start > date:
                continue
            if version.coverage_amount_revaluation:
                continue
            if version.coverage_amount:
                return version.coverage_amount
            cls.append_error(args, 'Coverage amount undefined')
            break

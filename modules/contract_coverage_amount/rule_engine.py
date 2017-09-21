# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

from trytond.modules.coog_core import fields
from trytond.modules.rule_engine import check_args

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
        cls.type_.selection.append(('coverage_amount_validation',
            'Coverage Amount Validation'))
        cls.type_.selection.append(('coverage_amount_selection',
            'Coverage Amount Selection'))

    @fields.depends('type_')
    def on_change_with_result_type(self, name=None):
        if self.type_ == 'coverage_amount_validation':
            return 'boolean'
        elif self.type_ == 'coverage_amount_selection':
            return 'list'
        return super(RuleEngine, self).on_change_with_result_type(name)


class RuleEngineRuntime:
    __metaclass__ = PoolMeta
    __name__ = 'rule_engine.runtime'

    @classmethod
    @check_args('option', 'date')
    def _re_get_coverage_amount(cls, args):
        option = cls.get_option(args)
        version = option.get_version_at_date(args['date'])
        if version.coverage_amount:
            return version.coverage_amount
        cls.append_error(args, 'Coverage amount undefined')

    @classmethod
    @check_args('option', 'date')
    def _re_get_other_coverage_amount(cls, args, coverage_code):
        return cls.get_other_option_data(coverage_code,
            '_re_get_coverage_amount', args)

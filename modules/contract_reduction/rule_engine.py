# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal

from trytond.pool import PoolMeta

from trytond.modules.coog_core import fields
from trytond.modules.rule_engine import check_args

__all__ = [
    'RuleEngine',
    'RuleRuntime',
    ]


class RuleEngine:
    __metaclass__ = PoolMeta
    __name__ = 'rule_engine'

    @classmethod
    def __setup__(cls):
        super(RuleEngine, cls).__setup__()
        cls.type_.selection += [
            ('reduction', 'Reduction'),
            ('reduction_eligibility', 'Reduction Eligibility'),
            ]

    @fields.depends('type_')
    def on_change_with_result_type(self, name=None):
        if self.type_ == 'reduction':
            return 'decimal'
        elif self.type_ == 'reduction_eligibility':
            return 'boolean'
        return super(RuleEngine, self).on_change_with_result_type(name)


class RuleRuntime:
    __metaclass__ = PoolMeta
    __name__ = 'rule_engine.runtime'

    @classmethod
    @check_args('contract')
    def _re_contract_reduction_date(cls, args):
        return args['contract'].reduction_date

    @classmethod
    @check_args('option')
    def _re_option_reduction_value(cls, args):
        return args['option'].reduction_value or Decimal(0)

# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

from trytond.modules.coog_core import fields
from trytond.modules.rule_engine import check_args

__metaclass__ = PoolMeta
__all__ = [
    'RuleEngineRuntime',
    'RuleEngine',
    ]


class RuleEngineRuntime:
    __name__ = 'rule_engine.runtime'

    @classmethod
    @check_args('contract')
    def _re_commission_plan(cls, args):
        contract = args['contract']
        if contract.agent:
            return contract.agent.plan.rule_engine_key

    @classmethod
    @check_args('amount')
    def _re_invoice_line_amount(cls, args):
        return args['amount']

    @classmethod
    @check_args('invoice_line')
    def _re_invoice_line_start_date(cls, args):
        if args['invoice_line']:
            return args['invoice_line'].coverage_start

    @classmethod
    @check_args('invoice_line')
    def _re_invoice_line_end_date(cls, args):
        if args['invoice_line']:
            return args['invoice_line'].coverage_end


class RuleEngine:
    __name__ = 'rule_engine'

    @classmethod
    def __setup__(cls):
        super(RuleEngine, cls).__setup__()
        cls.type_.selection.append(('commission', 'Commission'))

    @fields.depends('type_')
    def on_change_with_result_type(self, name=None):
        if self.type_ == 'commission':
            return 'decimal'
        return super(RuleEngine, self).on_change_with_result_type(name)

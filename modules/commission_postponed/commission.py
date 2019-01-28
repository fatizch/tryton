# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Literal

from trytond.pool import Pool, PoolMeta
from trytond.server_context import ServerContext
from trytond.pyson import Bool, Eval, If
from trytond.model import ModelView
from trytond.transaction import Transaction

from trytond.modules.rule_engine import get_rule_mixin
from trytond.modules.coog_core import utils, fields

__all__ = [
    'Commission',
    'AggregatedCommission',
    'PlanLines',
    'CreateInvoice',
    ]


class Commission(metaclass=PoolMeta):
    __name__ = 'commission'

    postponed = fields.Boolean('Is Postponed', select=True, readonly=True,
        help='The commission amount will be calculated by batch treatment')

    @classmethod
    def __setup__(cls):
        super(Commission, cls).__setup__()
        cls.amount.depends += ['postponed']
        cls.amount.domain = [
            If(Bool(Eval('postponed')), [('amount', '=', 0)],
                cls.amount.domain)]

    @classmethod
    def default_postponed(cls):
        return False

    @classmethod
    @ModelView.button
    def create_waiting_move(cls, commissions):
        # will only be called if commission_waiting_cog is installed
        with_waiting_move = [x for x in commissions if not x.postponed]
        if with_waiting_move:
            super(Commission, cls).create_waiting_move(with_waiting_move)

    @classmethod
    def calculate_postponed_commission_amount(cls, commissions):
        pool = Pool()
        Currency = pool.get('currency.currency')
        Commission = pool.get('commission')
        all_commissions = []
        with ServerContext().set_context(postponed_calculation=True):
            for commission in commissions:
                if not commission.postponed:
                    raise ValueError
                if commission.origin.__name__ == 'account.invoice.line':
                    invoice_line = commission.origin
                    plan = commission.agent.plan
                    with Transaction().set_context(
                            date=commission.origin.invoice.currency_date):
                        base_amount = Currency.compute(
                            invoice_line.invoice.currency, invoice_line.amount,
                            commission.agent.currency, round=False)
                    if invoice_line.invoice.type == 'out_credit_note':
                        base_amount *= -1
                    pattern = invoice_line._get_commission_pattern(plan,
                        commission.agent, commission.start, commission.end)
                    plan_line = plan.get_matching_line(pattern)
                    context = invoice_line.get_commission_calculation_context(
                        commission.start, commission.end, plan_line,
                        base_amount, pattern)
                    invoice_line.update_commission_amount_and_rate(
                        commission, plan_line, context)
                    commission.postponed = False
                    all_commissions.append(commission)
                else:
                    raise NotImplementedError
        if all_commissions:
            Commission.save(all_commissions)
            if utils.is_module_installed('commission_waiting_cog'):
                Commission.create_waiting_move(all_commissions)


class AggregatedCommission(metaclass=PoolMeta):
    __name__ = 'commission.aggregated'

    @classmethod
    def get_where_clause(cls, tables):
        commission = tables['commission']
        clause = super(AggregatedCommission, cls).get_where_clause(tables)
        return clause & (commission.postponed != Literal(True))


class PlanLines(get_rule_mixin('postponement_rule', 'Postponement Rule'),
        metaclass=PoolMeta):
    __name__ = 'commission.plan.line'

    @classmethod
    def __setup__(cls):
        super(PlanLines, cls).__setup__()
        cls.postponement_rule.domain = [('type_', '=', 'commission')]
        cls.postponement_rule.help = "This rule should return True or False " \
            "to indicate if the commission amount calculation should be " \
            "postponed."


class CreateInvoice(metaclass=PoolMeta):
    __name__ = 'commission.create_invoice'

    @classmethod
    def _get_commission_insurance_where_clause(cls, tables):
        commission = tables['commission']
        return super(CreateInvoice,
            cls)._get_commission_insurance_where_clause(tables
                ) & (commission.postponed != Literal(True))

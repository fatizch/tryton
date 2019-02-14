# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from decimal import Decimal
from trytond.server_context import ServerContext

__all__ = [
    'Invoice',
    'InvoiceLine',
    ]


class Invoice(metaclass=PoolMeta):
    __name__ = 'account.invoice'

    @classmethod
    def _get_commissions_to_delete(cls, ids):
        to_delete = super(Invoice, cls)._get_commissions_to_delete(ids)
        Commission = Pool().get('commission')
        postponed = Commission.search([
                ('postponed', '=', True),
                ('origin.invoice', 'in', ids, 'account.invoice.line'),
                ])
        return to_delete + postponed

    @classmethod
    def _get_commissions_to_cancel(cls, ids):
        to_cancel = super(Invoice, cls)._get_commissions_to_cancel(ids)
        return [x for x in to_cancel if not x.postponed]


class InvoiceLine(metaclass=PoolMeta):
    __name__ = 'account.invoice.line'

    def commission_to_save(self, commission):
        return super(InvoiceLine, self).commission_to_save(commission) or \
            commission.postponed

    def update_commission_from_plan_line(self, commission, plan_line, context):
        self.update_commission_postponement(commission, plan_line, context)
        super(InvoiceLine, self).update_commission_from_plan_line(commission,
            plan_line, context)

    def update_commission_postponement(self, commission, plan_line, context):
        if ServerContext().get('postponed_calculation'):
            return
        args = plan_line.get_rule_engine_args_from_context(context)
        postpone = plan_line.calculate_postponement_rule(args)
        commission.postponed = bool(postpone)

    def update_commission_amount_and_rate(self, commission, plan_line, context):
        if not ServerContext().get('postponed_calculation') and \
                getattr(commission, 'postponed', False):
            commission.amount = Decimal('0')
            commission.commission_rate = Decimal('0')
        else:
            super(InvoiceLine, self).update_commission_amount_and_rate(
                commission, plan_line, context)

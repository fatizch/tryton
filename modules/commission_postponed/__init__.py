# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from . import commission
from . import invoice
from . import batch
from . import rule_engine
from . import slip


def register():
    Pool.register(
        commission.Commission,
        commission.AggregatedCommission,
        commission.PlanLines,
        invoice.Invoice,
        invoice.InvoiceLine,
        rule_engine.RuleEngineRuntime,
        batch.CommissionPostponedCalculate,
        batch.CreateCommissionInvoiceBatch,
        module='commission_postponed', type_='model')
    Pool.register(
        commission.CreateInvoice,
        module='commission_postponed', type_='wizard')
    Pool.register(
        slip.InvoiceSlipConfiguration,
        module='commission_postponed', type_='model',
        depends=['commission_insurer'])

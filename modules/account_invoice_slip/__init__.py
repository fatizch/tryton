# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from . import slip
from . import wizard
from . import account
from . import batch
from . import account_insurer_batch
from . import insurer


def register():
    Pool.register(
        slip.InvoiceSlipConfiguration,
        slip.InvoiceSlipAccount,
        wizard.InvoiceSlipParameters,
        account.MoveLine,
        account.Invoice,
        account.InvoiceLine,
        account.Journal,
        batch.CreateEmptySlipBatch,
        batch.LinkSlipBatch,
        batch.FinalizeSlipBatch,
        module='account_invoice_slip', type_='model')
    Pool.register(
        wizard.CreateSlip,
        module='account_invoice_slip', type_='wizard')
    Pool.register(
        insurer.Insurer,
        insurer.InsurerSlipConfiguration,
        insurer.CreateInsurerSlipParameters,
        account_insurer_batch.CreateEmptyInvoicePrincipalBatch,
        account_insurer_batch.LinkInvoicePrincipalBatch,
        account_insurer_batch.FinalizeInvoicePrincipalBatch,
        module='account_invoice_slip', type_='model',
        depends=['offered_insurance'])
    Pool.register(
        insurer.CreateInsurerSlip,
        module='account_invoice_slip', type_='wizard',
        depends=['offered_insurance'])

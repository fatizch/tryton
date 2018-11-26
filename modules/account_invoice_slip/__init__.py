# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from . import slip
from . import wizard
from . import account
from . import batch


def register():
    Pool.register(
        slip.InvoiceSlipConfiguration,
        slip.InvoiceSlipAccount,
        wizard.InvoiceSlipParameters,
        account.MoveLine,
        account.Invoice,
        batch.CreateEmptySlipBatch,
        batch.LinkSlipBatch,
        batch.FinalizeSlipBatch,
        module='account_invoice_slip', type_='model')
    Pool.register(
        wizard.CreateSlip,
        module='account_invoice_slip', type_='wizard')

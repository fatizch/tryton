# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import commission
import account
import party
import invoice
import batch
import configuration


def register():
    Pool.register(
        commission.Agent,
        commission.Commission,
        commission.CreateInvoicePrincipalAsk,
        account.MoveLine,
        account.InvoiceLine,
        account.Invoice,
        party.Insurer,
        invoice.Invoice,
        configuration.Configuration,
        batch.CreateEmptyInvoicePrincipalBatch,
        batch.LinkInvoicePrincipalBatch,
        batch.FinalizeInvoicePrincipalBatch,
        module='commission_insurer', type_='model')
    Pool.register(
        commission.CreateInvoicePrincipal,
        module='commission_insurer', type_='wizard')

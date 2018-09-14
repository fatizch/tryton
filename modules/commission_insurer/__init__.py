# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import commission
import account
import invoice
import configuration
import offered
import batch
import party
import report_engine


def register():
    Pool.register(
        commission.Agent,
        commission.Commission,
        commission.CreateInvoicePrincipalAsk,
        account.MoveLine,
        account.InvoiceLine,
        account.Invoice,
        invoice.Invoice,
        configuration.Configuration,
        offered.OptionDescription,
        batch.CreateEmptyInvoicePrincipalBatch,
        batch.LinkInvoicePrincipalBatch,
        batch.FinalizeInvoicePrincipalBatch,
        party.Insurer,
        report_engine.ReportTemplate,
        module='commission_insurer', type_='model')
    Pool.register(
        commission.CreateInvoicePrincipal,
        module='commission_insurer', type_='wizard')

# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from . import commission
from . import invoice
from . import configuration
from . import offered
from . import slip
from . import batch
from . import party
from . import report_engine


def register():
    Pool.register(
        commission.Agent,
        commission.CreateInvoicePrincipalAsk,
        invoice.Invoice,
        slip.InvoiceSlipConfiguration,
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

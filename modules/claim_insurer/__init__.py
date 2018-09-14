# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import party
import commission
import account
import report_engine


def register():
    Pool.register(
        party.Insurer,
        commission.Commission,
        commission.CreateInvoicePrincipalAsk,
        account.Invoice,
        account.InvoiceLine,
        report_engine.ReportTemplate,
        module='claim_insurer', type_='model')

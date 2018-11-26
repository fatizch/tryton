# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from . import party
from . import invoice
from . import report_engine
from . import move
from . import configuration
from . import payment_term
from . import wizard
from . import event
from . import period
from . import load_data


def register():
    Pool.register(
        invoice.InvoiceLine,
        invoice.Invoice,
        invoice.InvoiceLineTax,
        party.Party,
        party.PartyPaymentTerm,
        party.PartyAccount,
        report_engine.ReportTemplate,
        move.Move,
        move.MoveLine,
        configuration.Configuration,
        payment_term.PaymentTerm,
        payment_term.PaymentTermLine,
        payment_term.PaymentTermLineRelativeDelta,
        wizard.SelectTerm,
        event.EventTypeAction,
        period.Period,
        module='account_invoice_cog', type_='model')

    Pool.register(
        wizard.ChangePaymentTerm,
        wizard.PartyErase,
        load_data.FiscalYearSetWizard,
        module='account_invoice_cog', type_='wizard')

# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
import party
import invoice
import report_engine
import move
import configuration
import payment_term
import wizard
import event
import period
import load_data


def register():
    Pool.register(
        invoice.InvoiceLine,
        invoice.Invoice,
        party.Party,
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
        load_data.FiscalYearSetWizard,
        module='account_invoice_cog', type_='wizard')

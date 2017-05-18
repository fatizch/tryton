# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
import test_case
import party
import invoice
import report_engine
import move
import configuration
import payment_term
import wizard


def register():
    Pool.register(
        invoice.InvoiceLine,
        invoice.Invoice,
        test_case.TestCaseModel,
        party.Party,
        report_engine.ReportTemplate,
        move.Move,
        move.MoveLine,
        configuration.Configuration,
        payment_term.PaymentTerm,
        payment_term.PaymentTermLine,
        payment_term.PaymentTermLineRelativeDelta,
        wizard.SelectTerm,
        module='account_invoice_cog', type_='model')

    Pool.register(
        wizard.ChangePaymentTerm,
        module='account_invoice_cog', type_='wizard')

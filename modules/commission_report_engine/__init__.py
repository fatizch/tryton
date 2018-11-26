# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from . import invoice_report
from . import invoice
from . import event


def register():
    Pool.register(
        invoice_report.InvoiceReportDefinition,
        invoice.Invoice,
        event.EventTypeAction,
        module='commission_report_engine', type_='model')

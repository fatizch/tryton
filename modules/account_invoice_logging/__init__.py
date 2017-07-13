# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
import invoice


def register():
    Pool.register(
        invoice.Invoice,
        invoice.InvoiceLogging,
        module='account_invoice_logging', type_='model')

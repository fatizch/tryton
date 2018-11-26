# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from . import invoice
from . import product
from . import party


def register():
    Pool.register(
        invoice.Invoice,
        invoice.InvoiceLine,
        product.Product,
        module='supplier_invoice_insurance', type_='model')
    Pool.register(
        party.PartyReplace,
        module='supplier_invoice_insurance', type_='wizard')

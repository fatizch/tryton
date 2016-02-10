from trytond.pool import Pool

from .invoice import *
from .product import *


def register():
    Pool.register(
        Invoice,
        InvoiceLine,
        Product,
        module='supplier_invoice_insurance', type_='model')

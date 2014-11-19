from trytond.pool import Pool
from .invoice import *


def register():
    Pool.register(
        Invoice,
        InvoiceLogging,
        module='account_invoice_logging', type_='model')

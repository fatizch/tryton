from trytond.pool import Pool

from .contract import *
from .invoice import *


def register():
    Pool.register(
        MigratorContract,
        MigratorInvoice,
        MigratorInvoiceLine,
        module='migrator_invoice', type_='model')

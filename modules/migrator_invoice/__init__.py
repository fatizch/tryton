from trytond.pool import Pool

from . import contract
from . import invoice


def register():
    Pool.register(
        contract.MigratorContract,
        invoice.MigratorInvoice,
        invoice.MigratorInvoiceLine,
        module='migrator_invoice', type_='model')

from trytond.pool import Pool

import contract
import invoice


def register():
    Pool.register(
        contract.MigratorContract,
        invoice.MigratorInvoice,
        invoice.MigratorInvoiceLine,
        module='migrator_invoice', type_='model')

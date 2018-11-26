from trytond.pool import Pool

from . import move
from . import invoice


def register():
    Pool.register(
        move.MigratorInvoiceMoveLine,
        move.MigratorMoveReconciliation,
        invoice.MigratorInvoice,
        module='migrator_move', type_='model')

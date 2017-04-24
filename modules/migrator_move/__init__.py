from trytond.pool import Pool

from .move import *
from .invoice import *


def register():
    Pool.register(
        MigratorInvoiceMoveLine,
        MigratorMoveReconciliation,
        MigratorInvoice,
        module='migrator_move', type_='model')

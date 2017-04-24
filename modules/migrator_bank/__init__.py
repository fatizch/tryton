# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from .bank import *

def register():
    Pool.register(
        MigratorBank,
        MigratorBankAccount,
        MigratorBankAgency,
        module='migrator_bank', type_='model')

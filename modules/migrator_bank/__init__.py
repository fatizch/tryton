# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from . import bank


def register():
    Pool.register(
        bank.MigratorBank,
        bank.MigratorBankAccount,
        bank.MigratorBankAgency,
        bank.MigratorSepaMandat,
        module='migrator_bank', type_='model')

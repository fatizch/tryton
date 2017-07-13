# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import loan
import party


def register():
    Pool.register(
        party.MigratorLender,
        loan.MigratorLoan,
        loan.MigratorLoanIncrement,
        module='migrator_loan', type_='model')

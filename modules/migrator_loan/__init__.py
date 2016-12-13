# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from .loan import *
from .party import *


def register():
    Pool.register(
        MigratorLender,
        MigratorLoan,
        MigratorLoanIncrement,
        module='migrator_loan', type_='model')

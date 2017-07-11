# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import bank
import test_case


def register():
    Pool.register(
        bank.Bank,
        bank.Agency,
        bank.BankAccount,
        test_case.TestCaseModel,
        module='bank_fr', type_='model')

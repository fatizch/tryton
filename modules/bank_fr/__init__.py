# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .bank import *
from .test_case import *


def register():
    Pool.register(
        Bank,
        Agency,
        BankAccount,
        TestCaseModel,
        module='bank_fr', type_='model')

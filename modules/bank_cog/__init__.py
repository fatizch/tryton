# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .party import *
from .bank import *
from .test_case import *


def register():
    Pool.register(
        # From Party
        Party,
        SynthesisMenuBankAccoount,
        SynthesisMenu,
        # From Bank
        Bank,
        BankAccount,
        BankAccountNumber,
        BankAccountParty,
        # from test_case
        TestCaseModel,
        module='bank_cog', type_='model')
    Pool.register(
        SynthesisMenuOpen,
        module='bank_cog', type_='wizard')

# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import party
import bank
import test_case


def register():
    Pool.register(
        party.Party,
        party.SynthesisMenuBankAccoount,
        party.SynthesisMenu,
        bank.Bank,
        bank.BankAccount,
        bank.BankAccountNumber,
        bank.BankAccountParty,
        test_case.TestCaseModel,
        module='bank_cog', type_='model')
    Pool.register(
        party.SynthesisMenuOpen,
        module='bank_cog', type_='wizard')

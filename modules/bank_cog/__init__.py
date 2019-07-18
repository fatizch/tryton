# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from . import party
from . import bank
from . import load_data
from . import test_case
from . import wizard
from . import api


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
        load_data.BankDataSet,
        module='bank_cog', type_='model')
    Pool.register(
        party.SynthesisMenuOpen,
        load_data.BankDataSetWizard,
        wizard.PartyErase,
        module='bank_cog', type_='wizard')

    Pool.register(
        api.APICore,
        api.APIParty,
        module='bank_cog', type_='model', depends=['api'])

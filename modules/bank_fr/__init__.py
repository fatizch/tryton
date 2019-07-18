# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from . import bank
from . import test_case
from . import load_data
from . import api


def register():
    Pool.register(
        bank.Bank,
        bank.Agency,
        bank.BankAccount,
        test_case.TestCaseModel,
        load_data.BankDataSet,
        module='bank_fr', type_='model')
    Pool.register(
        load_data.BankDataSetWizard,
        module='bank_fr', type_='wizard')

    Pool.register(
        api.APIParty,
        module='bank_fr', type_='model', depends=['api'])

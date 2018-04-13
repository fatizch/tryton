# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
import contract
import party
import wizard


def register():
    Pool.register(
        contract.Contract,
        contract.ContractOption,
        contract.Beneficiary,
        module='contract_life_clause', type_='model')
    Pool.register(
        party.PartyReplace,
        wizard.PartyErase,
        module='contract_life_clause', type_='wizard')

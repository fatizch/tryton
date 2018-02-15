# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
import contract
import account
import wizard
import dunning
import move
import payment
import batch


def register():
    Pool.register(
        contract.Contract,
        contract.ContractSet,
        account.Fee,
        dunning.Level,
        move.PartyBalance,
        payment.Payment,
        batch.RenewContracts,
        module='contract_set_insurance_invoice', type_='model')
    Pool.register(
        contract.DisplayContractSetPremium,
        wizard.Renew,
        module='contract_set_insurance_invoice', type_='wizard')

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
        module='contract_set_insurance_invoice', type_='model')
    Pool.register(
        contract.DisplayContractSetPremium,
        module='contract_set_insurance_invoice', type_='wizard')
    Pool.register(
        dunning.Level,
        module='contract_set_insurance_invoice', type_='model',
        depends=['contract_insurance_invoice_dunning'])
    Pool.register(
        move.PartyBalance,
        module='contract_set_insurance_invoice', type_='model',
        depends=['account_party_balance'])
    Pool.register(
        batch.RenewContracts,
        module='contract_set_insurance_invoice', type_='model',
        depends=['contract_term_renewal'])
    Pool.register(
        payment.Payment,
        module='contract_set_insurance_invoice', type_='model',
        depends=['contract_term_renewal'])
    Pool.register(
        wizard.Renew,
        module='contract_set_insurance_invoice', type_='wizard',
        depends=['contract_term_renewal'])

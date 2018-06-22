# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import rule_engine
import offered
import contract
import batch
import wizard
import endorsement


def register():
    Pool.register(
        rule_engine.RuleEngine,
        rule_engine.RuleRuntime,
        offered.OptionDescription,
        offered.OptionDescriptionReductionRule,
        contract.Contract,
        contract.Option,
        wizard.ReduceParameters,
        wizard.ReducePreview,
        module='contract_reduction', type_='model')
    Pool.register(
        wizard.Reduce,
        wizard.CancelReduction,
        module='contract_reduction', type_='wizard')
    Pool.register(
        endorsement.Endorsement,
        module='contract_reduction', type_='model',
        depends=['endorsement'])
    Pool.register(
        batch.CreateInvoiceContractBatch,
        module='contract_reduction', type_='model',
        depends=['contract_insurance_invoice'])
    Pool.register(
        endorsement.StartEndorsement,
        module='contract_reduction', type_='wizard',
        depends=['endorsement'])

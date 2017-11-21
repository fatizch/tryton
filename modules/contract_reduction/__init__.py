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
        endorsement.Endorsement,
        rule_engine.RuleEngine,
        offered.OptionDescription,
        offered.OptionDescriptionReductionRule,
        contract.Contract,
        contract.Option,
        batch.CreateInvoiceContractBatch,
        wizard.ReduceParameters,
        wizard.ReducePreview,
        module='contract_reduction', type_='model')

    Pool.register(
        wizard.Reduce,
        endorsement.StartEndorsement,
        module='contract_reduction', type_='wizard')

# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import offered
import contract
import party
import wizard
import rule_engine


def register():
    Pool.register(
        offered.Product,
        offered.OptionDescription,
        contract.Contract,
        contract.Option,
        contract.CoveredElement,
        party.Party,
        wizard.TransferCoveredElementsContracts,
        wizard.TransferCoveredElementsItemDescs,
        wizard.TransferCoveredElementsItemDescLine,
        rule_engine.RuleEngineRuntime,
        module='contract_group', type_='model')

    Pool.register(
        wizard.TransferCoveredElements,
        module='contract_group', type_='wizard')

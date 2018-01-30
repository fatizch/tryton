# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import rule_engine
import invoice
import offered
import configuration
import contract
import wizard


def register():
    Pool.register(
        rule_engine.RuleEngine,
        invoice.Invoice,
        offered.OptionDescription,
        offered.OptionDescriptionSurrenderRule,
        configuration.Configuration,
        contract.Contract,
        contract.Option,
        wizard.SurrenderParameters,
        wizard.SurrenderPreview,
        wizard.ValidateSurrenderParameters,
        module='contract_surrender', type_='model')

    Pool.register(
        wizard.PlanSurrender,
        wizard.ValidateSurrender,
        wizard.CancelSurrender,
        module='contract_surrender', type_='wizard')

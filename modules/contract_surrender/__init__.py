# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from . import rule_engine
from . import invoice
from . import offered
from . import configuration
from . import contract
from . import wizard


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

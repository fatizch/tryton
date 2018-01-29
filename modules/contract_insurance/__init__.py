# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import event
import contract
import party
import report_engine
import wizard
import rule_engine
import batch

from trytond.modules.coog_core import expand_tree
CoveredElementTreeExpansion = expand_tree('contract.covered_element')
OptionTreeExpansion = expand_tree('contract.option')


def register():
    Pool.register(
        event.EventTypeAction,
        event.EventLog,
        party.Party,
        contract.Contract,
        contract.CoveredElement,
        contract.CoveredElementVersion,
        contract.ContractOption,
        contract.ContractOptionVersion,
        CoveredElementTreeExpansion,
        contract.CoveredElementPartyRelation,
        contract.ExtraPremium,
        contract.OptionExclusionKindRelation,
        OptionTreeExpansion,
        report_engine.ReportTemplate,
        wizard.OptionsDisplayer,
        wizard.WizardOption,
        wizard.ExtraPremiumSelector,
        wizard.CreateExtraPremiumOptionSelector,
        wizard.OptionSelector,
        wizard.ExclusionOptionSelector,
        wizard.ExtraPremiumDisplay,
        wizard.ExclusionSelector,
        wizard.ExclusionDisplay,
        rule_engine.RuleEngineRuntime,
        batch.ContractDocumentRequestCreation,
        module='contract_insurance', type_='model')

    Pool.register(
        wizard.OptionSubscription,
        wizard.ManageExtraPremium,
        wizard.ManageExclusion,
        wizard.CreateExtraPremium,
        party.PartyReplace,
        module='contract_insurance', type_='wizard')

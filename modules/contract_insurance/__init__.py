# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from . import event
from . import contract
from . import party
from . import report_engine
from . import wizard
from . import rule_engine
from . import batch
from . import api

from trytond.modules.coog_core import expand_tree
CoveredElementTreeExpansion = expand_tree('contract.covered_element')
OptionTreeExpansion = expand_tree('contract.option')


def register():
    Pool.register(
        event.EventTypeAction,
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
        wizard.PackageSelectionPerCovered,
        wizard.PackageSelection,
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
        batch.PartyAnonymizeIdentificationBatch,
        module='contract_insurance', type_='model')

    Pool.register(
        wizard.OptionSubscription,
        wizard.ManageExtraPremium,
        wizard.ManageExclusion,
        wizard.CreateExtraPremium,
        party.PartyReplace,
        wizard.PartyErase,
        module='contract_insurance', type_='wizard')

    Pool.register(
        event.EventLog,
        module='contract_insurance', type_='model',
        depends=['event_log'])

    Pool.register(
        api.APIContract,
        api.RuleEngine,
        module='contract_insurance', type_='model', depends=['api'])

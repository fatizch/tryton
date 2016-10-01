# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from .event import *
from .contract import *
from .party import *
from .report_engine import *
from .wizard import *
from .rule_engine import *

from trytond.modules.coog_core import expand_tree
CoveredElementTreeExpansion = expand_tree('contract.covered_element')
OptionTreeExpansion = expand_tree('contract.option')


def register():
    Pool.register(
        EventLog,
        Party,
        Contract,
        CoveredElement,
        CoveredElementVersion,
        ContractOption,
        ContractOptionVersion,
        CoveredElementTreeExpansion,
        CoveredElementPartyRelation,
        ExtraPremium,
        OptionExclusionKindRelation,
        OptionTreeExpansion,
        ReportTemplate,
        OptionsDisplayer,
        WizardOption,
        ExtraPremiumSelector,
        CreateExtraPremiumOptionSelector,
        OptionSelector,
        ExclusionOptionSelector,
        ExtraPremiumDisplay,
        ExclusionSelector,
        ExclusionDisplay,
        RuleEngineRuntime,
        module='contract_insurance', type_='model')

    Pool.register(
        OptionSubscription,
        ManageExtraPremium,
        ManageExclusion,
        CreateExtraPremium,
        module='contract_insurance', type_='wizard')

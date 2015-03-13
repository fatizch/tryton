from trytond.pool import Pool
from .contract import *
from .party import *
from .report_engine import *
from .renewal import *
from .wizard import *
from .service import *
from .rule_engine import *

from trytond.modules.cog_utils import expand_tree
CoveredElementTreeExpansion = expand_tree('contract.covered_element')
OptionTreeExpansion = expand_tree('contract.option')


def register():
    Pool.register(
        Party,
        Contract,
        CoveredElement,
        ContractOption,
        CoveredElementTreeExpansion,
        CoveredElementPartyRelation,
        ExtraPremium,
        OptionExclusionKindRelation,
        OptionTreeExpansion,
        ReportTemplate,
        ContractService,
        Expense,
        RenewalStart,
        RenewalResult,
        OptionsDisplayer,
        WizardOption,
        ExtraPremiumSelector,
        CreateExtraPremiumOptionSelector,
        OptionSelector,
        ExtraPremiumDisplay,
        ExclusionSelector,
        ExclusionDisplay,
        RuleEngineRuntime,
        module='contract_insurance', type_='model')

    Pool.register(
        RenewalWizard,
        OptionSubscription,
        ManageExtraPremium,
        ManageExclusion,
        CreateExtraPremium,
        module='contract_insurance', type_='wizard')

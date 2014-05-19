from trytond.pool import Pool
from .contract import *
from .party import *
from .document import *
from .renewal import *
from .rule_engine import *
from .wizard import *
from .service import *

from trytond.modules.cog_utils import expand_tree
CoveredElementTreeExpansion = expand_tree('contract.covered_element')
OptionTreeExpansion = expand_tree('contract.option')


def register():
    Pool.register(
        # From party
        Party,
        # From contract
        Contract,
        ContractAgreementRelation,
        CoveredElement,
        ContractOption,
        CoveredElementTreeExpansion,
        CoveredElementPartyRelation,
        ExtraPremium,
        OptionExclusionKindRelation,
        OptionTreeExpansion,
        # From document
        DocumentRequestLine,
        DocumentRequest,
        DocumentReceiveRequest,
        DocumentTemplate,
        # From Service
        ContractService,
        Expense,
        # from renewal
        RenewalStart,
        RenewalResult,
        #From Rule Engine,
        RuleEngineRuntime,
        #From Wizard
        OptionsDisplayer,
        WizardOption,
        ExtraPremiumSelector,
        OptionSelector,
        ExtraPremiumDisplay,
        ExclusionSelector,
        ExclusionDisplay,
        ExtraPremiumDisplayer,
        module='contract_insurance', type_='model')

    Pool.register(
        RenewalWizard,
        OptionSubscription,
        ManageExtraPremium,
        ManageExclusion,
        CreateExtraPremium,
        module='contract_insurance', type_='wizard')

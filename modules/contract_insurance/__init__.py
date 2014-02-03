from trytond.pool import Pool
from contract import *
from .party import *
from .document import *
from .renewal import *
from .rule_engine import *
from .wizard import *
from .clause import *
from .service import *

from trytond.modules.cog_utils import expand_tree
CoveredElementTreeExpansion = expand_tree('contract.covered_element')
CoveredDataTreeExpansion = expand_tree('contract.covered_data')


def register():
    Pool.register(
        # From party
        Party,
        # From contract
        Contract,
        ContractAgreementRelation,
        ContractOption,
        CoveredElement,
        CoveredElementTreeExpansion,
        CoveredElementPartyRelation,
        CoveredData,
        ExtraPremium,
        CoveredDataExclusionKindRelation,
        CoveredDataTreeExpansion,
        # From document
        DocumentRequestLine,
        DocumentRequest,
        DocumentReceiveRequest,
        # From Service
        ContractService,
        Expense,
        # From Clause
        ContractClause,
        # from renewal
        RenewalStart,
        RenewalResult,
        #From Rule Engine,
        RuleEngineRuntime,
        #From Wizard
        OptionsDisplayer,
        ExtraPremiumSelector,
        CoveredDataSelector,
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

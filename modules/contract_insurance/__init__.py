from trytond.pool import Pool
from .contract import *
from .party import *
from .document import *
from .renewal import *
from .wizard import *
from .service import *

from trytond.modules.cog_utils import expand_tree
CoveredElementTreeExpansion = expand_tree('contract.covered_element')
OptionTreeExpansion = expand_tree('contract.option')


def register():
    Pool.register(
        Party,
        Contract,
        ContractAgreementRelation,
        CoveredElement,
        ContractOption,
        CoveredElementTreeExpansion,
        CoveredElementPartyRelation,
        ExtraPremium,
        OptionExclusionKindRelation,
        OptionTreeExpansion,
        DocumentRequestLine,
        DocumentRequest,
        DocumentReceiveRequest,
        DocumentTemplate,
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
        module='contract_insurance', type_='model')

    Pool.register(
        RenewalWizard,
        OptionSubscription,
        ManageExtraPremium,
        ManageExclusion,
        CreateExtraPremium,
        module='contract_insurance', type_='wizard')

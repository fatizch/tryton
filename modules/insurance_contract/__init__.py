from trytond.pool import Pool
from contract import *
from subs_process import *
from .party import *
from .document import *

from trytond.modules.coop_utils import expand_tree
CoveredElementTreeExpansion = expand_tree('ins_contract.covered_element')
CoveredDataTreeExpansion = expand_tree('ins_contract.covered_data')


def register():
    Pool.register(
        # contract.py classes
        Party,
        InsurancePolicy,
        ContractHistory,
        ManagementRole,
        InsuranceSubscribedCoverage,
        SubscribedCoverageComplement,
        StatusHistory,
        CoveredElement,
        CoveredElementTreeExpansion,
        CoveredElementPartyRelation,
        CoveredData,
        CoveredDataTreeExpansion,
        Document,
        DocumentRequest,
        # subs_process.py classes
        # ProjectState,
        # CoverageDisplayer,
        # OptionSelectionState,
        # CoveredDesc,
        # SubscriptionProcessState,
        # SummaryState,
        DeliveredService,
        RequestFinder,
        Expense,
        module='insurance_contract', type_='model')

from trytond.pool import Pool
from contract import *
from subs_process import *
from billing import *
from billing_process import *
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
        ManagementProtocol,
        ManagementRole,
        InsuranceSubscribedCoverage,
        StatusHistory,
        BillingManager,
        CoveredElement,
        CoveredElementTreeExpansion,
        CoveredElementPartyRelation,
        CoveredData,
        CoveredDataTreeExpansion,
        PriceLine,
        Document,
        DocumentRequest,
        # subs_process.py classes
        # ProjectState,
        # CoverageDisplayer,
        # OptionSelectionState,
        # CoveredDesc,
        # SubscriptionProcessState,
        # SummaryState,
        # PricingLine,
        # billing.py classes
        Bill,
        GenericBillLine,
        # billing_process.py classes
        BillParameters,
        BillDisplay,
        DeliveredService,
        RequestFinder,
        Expense,
        ContractAddress,
        module='insurance_contract', type_='model')
    Pool.register(
        # subs_process.py classes
        # SubscriptionProcess,
        # billing_process.py classes
        BillingProcess,
        module='insurance_contract', type_='wizard')

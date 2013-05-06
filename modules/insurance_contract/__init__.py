from trytond.pool import Pool
from contract import *
from subs_process import *
from billing import *
from billing_process import *
from .party import *
from .document import *


def register():
    Pool.register(
        # contract.py classes
        Party,
        Contract,
        ContractHistory,
        ManagementProtocol,
        ManagementRole,
        Option,
        StatusHistory,
        BillingManager,
        CoveredElement,
        CoveredElementPartyRelation,
        CoveredData,
        PriceLine,
        Document,
        DocumentRequest,
        # subs_process.py classes
        ProjectState,
        CoverageDisplayer,
        OptionSelectionState,
        CoveredDesc,
        SubscriptionProcessState,
        SummaryState,
        PricingLine,
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
        SubscriptionProcess,
        # billing_process.py classes
        BillingProcess,
        module='insurance_contract', type_='wizard')

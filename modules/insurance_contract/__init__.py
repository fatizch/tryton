from trytond.pool import Pool
from contract import *
from subs_process import *
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
        CoveredElement,
        CoveredElementPartyRelation,
        CoveredData,
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
        ContractAddress,
        module='insurance_contract', type_='model')

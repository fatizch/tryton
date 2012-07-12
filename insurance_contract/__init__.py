from trytond.pool import Pool
from contract import *
from subs_process import *
from billing import *
from billing_process import *


def register():
    Pool.register(
        # contract.py classes
        SubscriptionManager,
        Contract,
        Option,
        BillingManager,
        CoveredElement,
        CoveredData,
        ExtensionLife,
        ExtensionCar,
        CoveredPerson,
        CoveredCar,
        PriceLine,
        # subs_process.py classes
        ProjectState,
        CoverageDisplayer,
        OptionSelectionState,
        CoveredDataDesc,
        CoveredPersonDesc,
        ExtensionLifeState,
        SubscriptionProcessState,
        BrokerManager,
        SummaryState,
        PricingLine,
        # billing.py classes
        GenericBillLine,
        Bill,
        # billing_process.py classes
        BillParameters,
        BillLineForDisplay,
        BillDisplay,
        BillingProcessState,
        module='insurance_contract', type_='model')
    Pool.register(
        # subs_process.py classes
        SubscriptionProcess,
        # billing_process.py classes
        BillingProcess,
        module='insurance_contract', type_='wizard')

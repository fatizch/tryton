from trytond.pool import Pool
from contract import *
from subs_process import *
from billing import *
from billing_process import *


def register():
    Pool.register(
        # contract.py classes
        GenericExtension,
        BrokerManager,
        Contract,
        Option,
        BillingManager,
        CoveredElement,
        CoveredData,
        PriceLine,
        # subs_process.py classes
        ProjectState,
        CoverageDisplayer,
        OptionSelectionState,
        CoveredDataDesc,
        SubscriptionProcessState,
        SummaryState,
        PricingLine,
        # billing.py classes
        Bill,
        GenericBillLine,
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

from trytond.pool import Pool
from contract import *
from subs_process import *


def register():
    Pool.register(
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
        ProjectState,
        CoverageDisplayer,
        OptionSelectionState,
        CoveredDataDesc,
        CoveredPersonDesc,
        ExtensionLifeState,
        SubscriptionProcessState,
        BrokerManager,
        module='insurance_contract', type_='model')
    Pool.register(
        SubscriptionProcess,
        module='insurance_contract', type_='wizard')

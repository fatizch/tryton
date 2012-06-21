from trytond.pool import Pool
from contract import *
from gbp_contract import *
from enrollment import *
from subs_process import *
from gbp_subs_process import *
from enrollment_process import *


def register():
    Pool.register(
        SubscriptionManager,
        Contract,
        GBPContract,
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
        ProjectGBPState,
        ExtensionGBPState,
        GBPSubscriptionProcessState,
        Enrollment,
        ProjectStateEnrollment,
        module='insurance_contract', type_='model')
    Pool.register(
        SubscriptionProcess,
        GBPSubscriptionProcess,
        EnrollmentProcess,
        module='insurance_contract', type_='wizard')

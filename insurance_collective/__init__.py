from trytond.pool import Pool
from .collective import *
from .contract import *
from .enrollment import *
from .gbp_subs_process import *
from .enrollment_process import *


def register():
    Pool.register(
        GroupProduct,
        GroupCoverage,
        GroupProductCoverageRelation,
        GroupPackageCoverage,
        Contract,
        GroupContract,
        StatusHistory,
        GroupBillingManager,
        GroupPriceLine,
        GroupOption,
        GroupCoveredElement,
        GroupCoveredData,
        GroupProductItemDescriptorRelation,
        GroupPricingRule,
        ProjectGBPState,
        ExtensionGBPState,
        GBPSubscriptionProcessState,
        Enrollment,
        EnrollmentProcessState,
        ProjectStateEnrollment,
        CoverageDisplayerForEnrollment,
        OptionSelectionStateForEnrollment,
        EnrollmentOption,
        GroupProductComplementaryDataRelation,
        GroupCoverageComplementaryDataRelation,
        module='insurance_collective', type_='model')
    Pool.register(
        GBPSubscriptionProcess,
        EnrollmentProcess,
        module='insurance_collective', type_='wizard')

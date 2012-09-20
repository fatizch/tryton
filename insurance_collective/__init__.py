from trytond.pool import Pool
from collective import *
from gbp_contract import *
from enrollment import *
from gbp_subs_process import *
from enrollment_process import *


def register():
    Pool.register(
        GroupBusinessRuleManager,
        GroupInsurancePlan,
        GroupInsuranceCoverage,
        GroupInsurancePlanOptionsCoverage,
        GroupGenericBusinessRule,
        GroupPricingData,
        GroupPriceCalculator,
        GroupPricingRule,
        GroupEligibilityRule,
        GroupBenefit,
        GroupBenefitRule,
        GroupEligibilityRelationKind,
        GroupReserveRule,
        GroupCoverageAmountRule,
        GBPContract,
        ProjectGBPState,
        ExtensionGBPState,
        GBPSubscriptionProcessState,
        Enrollment,
        EnrollmentProcessState,
        ProjectStateEnrollment,
        CoverageDisplayerForEnrollment,
        OptionSelectionStateForEnrollment,
        EnrollmentOption,
        module='insurance_collective', type_='model')
    Pool.register(
        GBPSubscriptionProcess,
        EnrollmentProcess,
        module='insurance_collective', type_='wizard')

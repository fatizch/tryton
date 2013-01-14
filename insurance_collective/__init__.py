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
        GroupContract,
        GroupOption,
        GroupCoveredElement,
        GroupCoveredData,
        GroupProductItemDescriptorRelation,
        GroupPricingRule,
        GroupPricingComponent,
        GroupEligibilityRule,
        GroupBenefit,
        GroupBenefitRule,
        GroupEligibilityRelationKind,
        GroupReserveRule,
        GroupCoverageAmountRule,
        GroupClauseRule,
        GroupClause,
        GroupClauseRelation,
        GroupClauseVersion,
        GroupTermRenewalRule,
        GroupDeductibleRule,
        ProjectGBPState,
        ExtensionGBPState,
        GBPSubscriptionProcessState,
        Enrollment,
        EnrollmentProcessState,
        ProjectStateEnrollment,
        CoverageDisplayerForEnrollment,
        OptionSelectionStateForEnrollment,
        EnrollmentOption,
        GroupProductSchemaElementRelation,
        GroupCoverageSchemaElementRelation,
        module='insurance_collective', type_='model')
    Pool.register(
        GBPSubscriptionProcess,
        EnrollmentProcess,
        module='insurance_collective', type_='wizard')

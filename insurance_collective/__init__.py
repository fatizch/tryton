from trytond.pool import Pool
from .collective import *
from .gbp_contract import *
from .enrollment import *
from .gbp_subs_process import *
from .enrollment_process import *


def register():
    Pool.register(
        GroupBusinessRuleManager,
        GBPContract,
        GroupInsurancePlan,
        GroupInsuranceCoverage,
        GroupPackageCoverage,
        GroupGenericBusinessRule,
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
        GroupDynamicDataManager,
        GroupSchemaElement,
        GroupSchemaElementRelation,
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
        module='insurance_collective', type_='model')
    Pool.register(
        GBPSubscriptionProcess,
        EnrollmentProcess,
        module='insurance_collective', type_='wizard')

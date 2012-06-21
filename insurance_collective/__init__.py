from trytond.pool import Pool
from collective import *


def register():
    Pool.register(
        GroupBusinessRuleManager,
        GroupInsurancePlan,
        GroupInsuranceCoverage,
        GroupInsurancePlanOptionsCoverage,
        GroupGenericBusinessRule,
        GroupPricingRule,
        GroupEligibilityRule,
        module='insurance_collective', type_='model')

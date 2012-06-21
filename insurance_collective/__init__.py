from trytond.pool import Pool
from collective import *


def register():
    Pool.register(
        GroupInsurancePlan,
        GroupInsuranceCoverage,
        GroupInsurancePlanOptionsCoverage,
        GroupBusinessRuleManager,
        GroupGenericBusinessRule,
        GroupPricingRule,
        GroupEligibilityRule,
        module='insurance_collective', type_='model')

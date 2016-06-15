from trytond.pool import Pool
from .benefit import *
from .contract import *


def register():
    Pool.register(
        BenefitRule,
        BenefitRuleIndemnification,
        BenefitRuleDeductible,
        Option,
        OptionVersion,
        OptionBenefit,
        module='claim_indemnification_group', type_='model')

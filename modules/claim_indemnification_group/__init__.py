# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .benefit import *
from .contract import *


def register():
    Pool.register(
        Benefit,
        BenefitRule,
        BenefitRuleIndemnification,
        BenefitRuleDeductible,
        BenefitRuleRevaluation,
        Option,
        OptionVersion,
        OptionBenefit,
        module='claim_indemnification_group', type_='model')

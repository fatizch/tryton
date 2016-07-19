# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .claim import *
from .rule_engine import *
from .benefit import *
from .contract import *
from .extra_data import *
from .wizard import *


def register():
    Pool.register(
        ClaimService,
        Salary,
        NetCalculationRule,
        NetCalculationRuleExtraData,
        BenefitRule,
        OptionBenefit,
        ExtraDatasDisplayers,
        IndemnificationDefinition,
        RuleEngineRuntime,
        RuleEngine,
        ExtraData,
        StartSetContributions,
        ContributionsView,
        module='claim_salary_fr', type_='model')
    Pool.register(
        CreateIndemnification,
        FillExtraData,
        SetContributions,
        module='claim_salary_fr', type_='wizard')

# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from .benefit import *
from .claim import *
from .runtime import *
from .wizard import *


def register():
    Pool.register(
        LossDescription,
        DeductionPeriodKind,
        LossDescriptionDeductionPeriodKindRelation,
        BenefitRule,
        Loss,
        DeductionPeriod,
        IndemnificationDefinition,
        RuleRuntime,
        module='claim_deduction_period', type_='model')

    Pool.register(
        CreateIndemnification,
        module='claim_deduction_period', type_='wizard')

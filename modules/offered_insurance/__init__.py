# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .rule_engine import *
from .offered import *
from .coverage import *
from .process import *
from .party import *
from .test_case import *
from .batch import *
from .exclusion import *
from .extra_premium import *


def register():
    Pool.register(
        Party,
        Insurer,
        ItemDescription,
        OptionDescription,
        Product,
        ItemDescSubItemDescRelation,
        ItemDescriptionExtraDataRelation,
        ProductValidationBatch,
        RuleEngineExtraData,
        RuleEngine,
        ExclusionKind,
        ExtraPremiumKind,
        RuleEngineRuntime,
        ProcessProductRelation,
        Process,
        TestCaseModel,
        module='offered_insurance', type_='model')

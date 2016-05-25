from trytond.pool import Pool
from .rule_engine import *
from .offered import *
from .expense import *
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
        ExpenseKind,
        TestCaseModel,
        module='offered_insurance', type_='model')

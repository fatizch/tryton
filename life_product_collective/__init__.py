from trytond.pool import Pool
from .product import *
from .tranche import *
from .college import *
from .society import *
from .gbp_creation import *


def register():
    Pool.register(
        GroupLifeCoverage,
        College,
        GroupPricingRule,
#        TrancheCalculatorLine,
        Tranche,
        CollegeTranche,
        Employee,
#        TrancheCalculator,
        CollegeDisplayer,
        TrancheDisplayer,
        CollegeSelection,
        TranchesSelection,
        module='life_product_collective', type_='model')

    Pool.register(
        GBPWizard,
        module='life_product_collective', type_='wizard')

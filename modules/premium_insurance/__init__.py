from trytond.pool import Pool

from .offered import *
from .contract import *

def register():
    Pool.register(
        Product,
        OptionDescription,
        OptionDescriptionPremiumRule,
        Contract,
        CoveredElement,
        ExtraPremium,
        module='premium_insurance', type_='model')

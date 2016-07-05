# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
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
        Premium,
        module='premium_insurance', type_='model')

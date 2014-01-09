from trytond.pool import Pool
from .benefit import *


def register():
    Pool.register(
        # From benefit
        Benefit,
        LossDescription,
        BenefitRule,
        module='benefit_life', type_='model')

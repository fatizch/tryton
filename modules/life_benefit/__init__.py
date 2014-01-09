from trytond.pool import Pool
from .benefit import *


def register():
    Pool.register(
        # From benefit
        Benefit,
        LossDescription,
        BenefitRule,
        module='life_benefit', type_='model')

from trytond.pool import Pool

from .product import *
from .contract import *


def register():
    Pool.register(
        # From Product
        Coverage,
        CollectiveRatingRule,
        TrancheRatingRule,
        #From Contract
        Contract,
        RateLine,
        module='life_billing_collective_fr', type_='model')

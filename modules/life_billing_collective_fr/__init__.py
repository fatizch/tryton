from trytond.pool import Pool

from .product import *
from .contract import *
from .billing import *


def register():
    Pool.register(
        # From Product
        Coverage,
        CollectiveRatingRule,
        FareClass,
        FareClassGroup,
        FareClassGroupFareClassRelation,
        SubRatingRule,
        #From Contract
        Contract,
        CoveredData,
        # From billing,
        RateLine,
        module='life_billing_collective_fr', type_='model')

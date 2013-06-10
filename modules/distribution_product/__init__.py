from trytond.pool import Pool

from .distribution import *
from .contract import *


def register():
    Pool.register(
        DistributionNetwork,
        Product,
        CommercialProduct,
        DistributionNetworkComProductRelation,
        Contract,
        module='distribution_product', type_='model')

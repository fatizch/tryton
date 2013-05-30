from trytond.pool import Pool

from .distribution import *


def register():
    Pool.register(
        DistributionNetwork,
        Product,
        CommercialProduct,
        DistributionNetworkComProductRelation,
        module='distribution_product', type_='model')

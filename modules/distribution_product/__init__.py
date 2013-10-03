from trytond.pool import Pool

from .distribution import *
from .contract import *
from .export import *


def register():
    Pool.register(
        DistributionNetwork,
        Product,
        CommercialProduct,
        DistributionNetworkComProductRelation,
        Contract,
        # from Export
        ExportPackage,
        module='distribution_product', type_='model')

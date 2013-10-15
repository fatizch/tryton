from trytond.pool import Pool

from .distribution import *
from .contract import *
from .export import *
from .test_case import *


def register():
    Pool.register(
        # from distribution
        DistributionNetwork,
        Product,
        CommercialProduct,
        DistributionNetworkComProductRelation,
        # from contract
        Contract,
        # from export
        ExportPackage,
        # from test_case
        TestCaseModel,
        module='distribution_product', type_='model')

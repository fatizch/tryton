from trytond.pool import Pool

from .distribution import *
from .offered import *
from .contract import *
from .export import *
from .test_case import *


def register():
    Pool.register(
        # from distribution
        DistributionNetwork,
        CommercialProduct,
        DistributionNetworkComProductRelation,
        # From Offered
        Product,
        # from contract
        Contract,
        # from export
        ExportPackage,
        # from test_case
        TestCaseModel,
        module='distribution_product', type_='model')

from trytond.pool import Pool

from .distribution import *
from .offered import *
from .contract import *
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
        CoveredElement,
        Beneficiary,
        # from test_case
        TestCaseModel,
        module='offered_distribution', type_='model')

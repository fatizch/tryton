# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import distribution
import offered
import contract
import test_case


def register():
    Pool.register(
        distribution.DistributionNetwork,
        distribution.CommercialProduct,
        distribution.DistributionNetworkComProductRelation,
        offered.Product,
        contract.Contract,
        test_case.TestCaseModel,
        module='offered_distribution', type_='model')

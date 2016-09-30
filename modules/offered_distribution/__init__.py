# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from .distribution import *
from .offered import *
from .contract import *
from .test_case import *


def register():
    Pool.register(
        DistributionNetwork,
        CommercialProduct,
        DistributionNetworkComProductRelation,
        Product,
        Contract,
        TestCaseModel,
        module='offered_distribution', type_='model')

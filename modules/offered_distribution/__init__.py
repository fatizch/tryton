# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from .distribution import *
from .offered import *
from .contract import *
from .test_case import *
from .rule_engine import *


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
        ContractBillingInformation,
        # from test_case
        TestCaseModel,
        RuleEngineRuntime,
        module='offered_distribution', type_='model')

# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import res
import distribution
import offered
import contract
import test_case
import process


def register():
    Pool.register(
        res.User,
        distribution.DistributionNetwork,
        distribution.CommercialProduct,
        distribution.DistributionNetworkComProductRelation,
        offered.Product,
        contract.Contract,
        test_case.TestCaseModel,
        process.ContractSubscribeFindProcess,
        module='contract_distribution', type_='model')
    Pool.register(
        process.ContractSubscribe,
        module='contract_distribution', type_='wizard')

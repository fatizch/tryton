# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import res
import distribution
import offered
import contract
import process


def register():
    Pool.register(
        res.User,
        distribution.DistributionNetwork,
        distribution.CommercialProduct,
        distribution.DistributionNetworkComProductRelation,
        offered.Product,
        contract.Contract,
        module='contract_distribution', type_='model')
    Pool.register(
        process.ContractSubscribeFindProcess,
        module='contract_distribution', type_='model',
        depends=['contract_process'])
    Pool.register(
        process.ContractSubscribe,
        module='contract_distribution', type_='wizard',
        depends=['contract_process'])

# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from . import distribution
from . import process
from . import contract
from . import rule_engine


def register():
    Pool.register(
        distribution.DistributionNetwork,
        distribution.DistributionChannel,
        distribution.DistributionNetworkChannelRelation,
        distribution.CommercialProduct,
        distribution.CommercialProductChannelRelation,
        process.Process,
        process.ProcessDistChannelRelation,
        process.ContractSubscribeFindProcess,
        contract.Contract,
        rule_engine.RuleEngineRuntime,
        module='distribution_channel', type_='model')

    Pool.register(
        process.ContractSubscribe,
        module='distribution_channel', type_='wizard',
        depends=['contract_process'])

# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import distribution
import configuration
import party
import contract
import process
import rule_engine


def register():
    Pool.register(
        distribution.DistributionNetwork,
        configuration.Configuration,
        configuration.ConfigurationDefaultPortfolio,
        party.Party,
        contract.Contract,
        contract.CoveredElement,
        contract.Beneficiary,
        contract.ContractBillingInformation,
        rule_engine.RuleEngineRuntime,
        module='distribution_portfolio', type_='model')

    Pool.register(
        process.ContractSubscribe,
        module='distribution_portfolio', type_='wizard')
